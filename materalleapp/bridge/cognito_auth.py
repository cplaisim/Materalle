"""
CognitoJWTAuthentication — DRF authentication for the hosted Django fallback.

The V2 primary path is frontend → WSS → Lambda (verifies JWT) → local Django
with an ``X-Bridge-Claims`` header. That path does not use this class.

The hosted fallback accepts direct HTTPS requests from the frontend when the
local bridge is unreachable. Those requests carry the Cognito ID token in the
``Authorization: Bearer`` header, so the hosted Django must verify JWTs itself.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

from jose import jwk, jwt
from jose.utils import base64url_decode
from rest_framework import authentication, exceptions

from .user import BridgeUser

logger = logging.getLogger(__name__)

_JWKS_CACHE: list | None = None


def _load_jwks(region: str, user_pool_id: str) -> list:
    global _JWKS_CACHE
    if _JWKS_CACHE is None:
        url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        with urllib.request.urlopen(url, timeout=5) as r:
            _JWKS_CACHE = json.loads(r.read())["keys"]
    return _JWKS_CACHE


def _verify(token: str) -> dict:
    region = os.environ["AWS_REGION_NAME"]
    user_pool_id = os.environ["COGNITO_USER_POOL_ID"]
    app_client_id = os.environ["COGNITO_APP_CLIENT_ID"]

    headers = jwt.get_unverified_headers(token)
    kid = headers["kid"]
    keys = _load_jwks(region, user_pool_id)
    key = next((k for k in keys if k["kid"] == kid), None)
    if key is None:
        raise exceptions.AuthenticationFailed("kid not in JWKS")

    public_key = jwk.construct(key)
    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())
    if not public_key.verify(message.encode(), decoded_sig):
        raise exceptions.AuthenticationFailed("signature verification failed")

    claims = jwt.get_unverified_claims(token)
    if claims["exp"] < time.time():
        raise exceptions.AuthenticationFailed("token expired")
    if claims.get("aud") != app_client_id and claims.get("client_id") != app_client_id:
        raise exceptions.AuthenticationFailed("wrong audience")
    if claims["iss"] != f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}":
        raise exceptions.AuthenticationFailed("wrong issuer")
    return claims


class CognitoJWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(self.keyword + " "):
            return None
        token = auth_header[len(self.keyword) + 1 :].strip()
        if not token:
            return None

        try:
            claims = _verify(token)
        except exceptions.AuthenticationFailed:
            raise
        except Exception as e:
            logger.warning("cognito JWT verification error: %s", e)
            raise exceptions.AuthenticationFailed("invalid token")

        user = BridgeUser(
            sub=claims.get("sub", ""),
            username=claims.get("cognito:username", claims.get("email", "")),
            role=claims.get("custom:role", "PARENT"),
            llm_backend=claims.get("custom:llm_backend", "ollama"),
            ollama_model=claims.get("custom:ollama_model", "llama3.2:1b"),
            email=claims.get("email", ""),
        )
        return (user, token)

    def authenticate_header(self, request):
        return self.keyword
