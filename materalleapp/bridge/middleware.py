"""
BridgeClaimsMiddleware — attaches a BridgeUser to ``request`` when the
request was dispatched via the AWS WebSocket bridge.

The bridge client injects an ``X-Bridge-Claims`` header containing the
JSON claims forwarded by the Lambda relay (already JWT-verified upstream).

For requests that did NOT come through the bridge (e.g. ``/admin/`` over
HTTP), this middleware is a no-op and Django's normal auth stack runs.
"""
from __future__ import annotations

import json
import logging

from .user import BridgeUser

logger = logging.getLogger(__name__)

BRIDGE_CLAIMS_HEADER = "HTTP_X_BRIDGE_CLAIMS"


class BridgeClaimsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        raw = request.META.get(BRIDGE_CLAIMS_HEADER)
        if raw:
            try:
                claims = json.loads(raw)
                request.user = BridgeUser(
                    sub=claims.get("sub", ""),
                    username=claims.get("username", ""),
                    role=claims.get("role", "PARENT"),
                    llm_backend=claims.get("llm_backend", "ollama"),
                    ollama_model=claims.get("ollama_model", "llama3.2:1b"),
                    email=claims.get("email", ""),
                )
                request._bridge_claims = claims
            except Exception as e:
                logger.warning("Failed to parse X-Bridge-Claims: %s", e)
        return self.get_response(request)
