"""
Materalle-2 V2 bridge Lambda.

Single Lambda handles three API Gateway WebSocket routes:
  - $connect     : authenticate + register connection in DynamoDB
  - $disconnect  : remove connection row
  - $default     : relay envelopes between frontend and local backend

Connection roles:
  - "backend" : the local Django WS client. Single instance (single daycare).
  - "frontend": an SPA user session. Keyed by Cognito sub.

Routing:
  - Frontend sends {type: "request", ...}  -> forward to backend connection.
  - Backend sends  {type: "response", ...} -> forward to target frontend.
"""
import json
import os
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError
from jose import jwt, jwk
from jose.utils import base64url_decode

REGION = os.environ["AWS_REGION_NAME"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["COGNITO_APP_CLIENT_ID"]
CONNECTIONS_TABLE = os.environ["CONNECTIONS_TABLE"]
BACKEND_SHARED_SECRET = os.environ["BACKEND_SHARED_SECRET"]

ddb = boto3.resource("dynamodb")
table = ddb.Table(CONNECTIONS_TABLE)

# JWKS cache (warm across invocations within a container)
_JWKS = None


def _load_jwks():
    global _JWKS
    if _JWKS is None:
        url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        with urllib.request.urlopen(url) as r:
            _JWKS = json.loads(r.read())["keys"]
    return _JWKS


def _verify_cognito_jwt(token: str) -> dict:
    """Verify a Cognito id_token and return its claims, or raise."""
    headers = jwt.get_unverified_headers(token)
    kid = headers["kid"]
    keys = _load_jwks()
    key = next((k for k in keys if k["kid"] == kid), None)
    if key is None:
        raise ValueError("kid not in JWKS")

    public_key = jwk.construct(key)
    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode())
    if not public_key.verify(message.encode(), decoded_sig):
        raise ValueError("Signature verification failed")

    claims = jwt.get_unverified_claims(token)
    if claims["exp"] < time.time():
        raise ValueError("Token expired")
    if claims.get("aud") != APP_CLIENT_ID and claims.get("client_id") != APP_CLIENT_ID:
        raise ValueError("Wrong audience")
    if claims["iss"] != f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}":
        raise ValueError("Wrong issuer")
    return claims


def _apigw_client(event):
    endpoint = (
        f"https://{event['requestContext']['domainName']}/"
        f"{event['requestContext']['stage']}"
    )
    return boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)


def _post(client, connection_id: str, payload: dict):
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode(),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "GoneException":
            # Stale connection — clean it up
            table.delete_item(Key={"connection_id": connection_id})
        else:
            raise


def _get_backend_connection_id() -> str | None:
    """Scan for the single active backend connection."""
    resp = table.query(
        IndexName="role-index",
        KeyConditionExpression="#r = :r",
        ExpressionAttributeNames={"#r": "role"},
        ExpressionAttributeValues={":r": "backend"},
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0]["connection_id"] if items else None


def _get_frontend_connection_id(user_sub: str) -> str | None:
    resp = table.query(
        IndexName="role-user-index",
        KeyConditionExpression="#r = :r AND user_sub = :u",
        ExpressionAttributeNames={"#r": "role"},
        ExpressionAttributeValues={":r": "frontend", ":u": user_sub},
        Limit=1,
        ScanIndexForward=False,
    )
    items = resp.get("Items", [])
    return items[0]["connection_id"] if items else None


# ── Route handlers ─────────────────────────────────────────────

def on_connect(event):
    conn_id = event["requestContext"]["connectionId"]
    qs = event.get("queryStringParameters") or {}
    ttl = int(time.time()) + 86400  # 24h

    backend_secret = qs.get("backend_secret")
    id_token = qs.get("id_token")

    if backend_secret:
        if backend_secret != BACKEND_SHARED_SECRET:
            return {"statusCode": 401, "body": "unauthorized"}
        # Enforce single-backend: remove any existing "backend" row first.
        existing = _get_backend_connection_id()
        if existing:
            table.delete_item(Key={"connection_id": existing})
        table.put_item(
            Item={
                "connection_id": conn_id,
                "role": "backend",
                "user_sub": "__backend__",
                "connected_at": int(time.time()),
                "ttl": ttl,
            }
        )
        return {"statusCode": 200, "body": "ok"}

    if id_token:
        try:
            claims = _verify_cognito_jwt(id_token)
        except Exception as e:
            return {"statusCode": 401, "body": f"unauthorized: {e}"}
        # Persist the full trusted claim set so $default can forward them
        # without re-verifying the JWT on every message.
        table.put_item(
            Item={
                "connection_id": conn_id,
                "role": "frontend",
                "user_sub": claims["sub"],
                "user_role": claims.get("custom:role", "PARENT"),
                "username": claims.get("cognito:username", claims.get("email", "")),
                "email": claims.get("email", ""),
                "llm_backend": claims.get("custom:llm_backend", "ollama"),
                "ollama_model": claims.get("custom:ollama_model", "llama3"),
                "token_exp": int(claims.get("exp", 0)),
                "connected_at": int(time.time()),
                "ttl": ttl,
            }
        )
        return {"statusCode": 200, "body": "ok"}

    return {"statusCode": 400, "body": "missing credentials"}


def on_disconnect(event):
    conn_id = event["requestContext"]["connectionId"]
    table.delete_item(Key={"connection_id": conn_id})
    return {"statusCode": 200, "body": "ok"}


def on_default(event):
    """Relay an envelope from frontend -> backend or backend -> frontend."""
    conn_id = event["requestContext"]["connectionId"]
    client = _apigw_client(event)

    try:
        envelope = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        _post(client, conn_id, {"type": "error", "message": "invalid JSON"})
        return {"statusCode": 200, "body": "ok"}

    sender = table.get_item(Key={"connection_id": conn_id}).get("Item")
    if not sender:
        _post(client, conn_id, {"type": "error", "message": "not connected"})
        return {"statusCode": 200, "body": "ok"}

    etype = envelope.get("type")

    if sender["role"] == "frontend" and etype == "request":
        # Claims were verified at $connect and stored in the connection row;
        # reuse them without re-verifying the JWT. Enforce the original token
        # expiry so a long-lived WS session cannot outlive its token.
        token_exp = int(sender.get("token_exp", 0) or 0)
        if token_exp and token_exp < int(time.time()):
            _post(client, conn_id, {
                "type": "response",
                "request_id": envelope.get("request_id"),
                "status": 401,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": "token expired — reconnect"}),
            })
            return {"statusCode": 200, "body": "ok"}

        backend_id = _get_backend_connection_id()
        if not backend_id:
            _post(client, conn_id, {
                "type": "response",
                "request_id": envelope.get("request_id"),
                "status": 503,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": "backend offline"}),
            })
            return {"statusCode": 200, "body": "ok"}

        # Rewrite envelope with trusted claims pulled from the connection row.
        forwarded = {
            "type": "request",
            "request_id": envelope.get("request_id"),
            "method": envelope.get("method", "GET"),
            "path": envelope.get("path", "/"),
            "headers": envelope.get("headers", {}),
            "body": envelope.get("body", ""),
            "origin_connection_id": conn_id,
            "claims": {
                "sub": sender["user_sub"],
                "username": sender.get("username", ""),
                "email": sender.get("email", ""),
                "role": sender.get("user_role", "PARENT"),
                "llm_backend": sender.get("llm_backend", "ollama"),
                "ollama_model": sender.get("ollama_model", "llama3"),
            },
        }
        _post(client, backend_id, forwarded)
        return {"statusCode": 200, "body": "ok"}

    if sender["role"] == "backend" and etype in ("response", "response_chunk"):
        target_conn = envelope.get("target_connection_id") or envelope.get("origin_connection_id")
        if not target_conn:
            return {"statusCode": 400, "body": "missing target"}
        _post(client, target_conn, envelope)
        return {"statusCode": 200, "body": "ok"}

    _post(client, conn_id, {"type": "error", "message": f"unexpected envelope type {etype} from {sender['role']}"})
    return {"statusCode": 200, "body": "ok"}


# ── Lambda entry ───────────────────────────────────────────────

def lambda_handler(event, context):
    route = event.get("requestContext", {}).get("routeKey")
    if route == "$connect":
        return on_connect(event)
    if route == "$disconnect":
        return on_disconnect(event)
    return on_default(event)
