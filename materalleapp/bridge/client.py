"""
Bridge client — outbound WebSocket to AWS API Gateway.

Opens a single persistent WSS connection authenticated with the shared
backend secret, then dispatches incoming ``request`` envelopes to the
local Django ASGI app and sends ``response`` envelopes back.

Envelope schema matches ``infra/terraform/v2/lambda/bridge/handler.py``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from urllib.parse import urlencode

import websockets
from django.core.handlers.asgi import ASGIHandler

logger = logging.getLogger(__name__)

# Exponential backoff bounds for reconnect loop
_RECONNECT_MIN = 1.0
_RECONNECT_MAX = 60.0


class BridgeClient:
    """Outbound WSS client that dispatches bridged requests to ASGI."""

    def __init__(self, endpoint: str, backend_secret: str):
        if not endpoint:
            raise ValueError("BRIDGE_WS_ENDPOINT is required")
        if not backend_secret:
            raise ValueError("BRIDGE_BACKEND_SECRET is required")
        self.endpoint = endpoint.rstrip("/")
        self.backend_secret = backend_secret
        self.asgi_app = ASGIHandler()
        self._ws = None

    @property
    def connect_url(self) -> str:
        return f"{self.endpoint}?{urlencode({'backend_secret': self.backend_secret})}"

    async def run_forever(self):
        """Connect + dispatch loop with exponential-backoff reconnect."""
        delay = _RECONNECT_MIN
        while True:
            try:
                logger.info("Bridge: connecting to %s", self.endpoint)
                async with websockets.connect(
                    self.connect_url,
                    ping_interval=30,
                    ping_timeout=20,
                    max_size=8 * 1024 * 1024,
                ) as ws:
                    self._ws = ws
                    logger.info("Bridge: connected")
                    delay = _RECONNECT_MIN
                    await self._dispatch_loop(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Bridge: connection error: %s", e)
            finally:
                self._ws = None

            logger.info("Bridge: reconnecting in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RECONNECT_MAX)

    async def _dispatch_loop(self, ws):
        async for raw in ws:
            try:
                envelope = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Bridge: invalid JSON from relay")
                continue
            if envelope.get("type") != "request":
                logger.debug("Bridge: ignoring envelope type %s", envelope.get("type"))
                continue
            # Fire-and-forget; responses are sent inside _handle_request.
            asyncio.create_task(self._handle_request(ws, envelope))

    async def _handle_request(self, ws, envelope: dict):
        request_id = envelope.get("request_id")
        origin = envelope.get("origin_connection_id")
        try:
            scope, body_bytes = self._build_scope(envelope)
            status, headers, body = await self._invoke_asgi(scope, body_bytes)
            reply = {
                "type": "response",
                "request_id": request_id,
                "origin_connection_id": origin,
                "status": status,
                "headers": {k.decode().lower(): v.decode() for k, v in headers},
                "body": body.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            logger.exception("Bridge: dispatch failed for %s", request_id)
            reply = {
                "type": "response",
                "request_id": request_id,
                "origin_connection_id": origin,
                "status": 500,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": str(e)}),
            }
        try:
            await ws.send(json.dumps(reply))
        except Exception as e:
            logger.warning("Bridge: failed to send response %s: %s", request_id, e)

    # ── ASGI plumbing ──────────────────────────────────────────

    def _build_scope(self, envelope: dict) -> tuple[dict, bytes]:
        method = (envelope.get("method") or "GET").upper()
        path = envelope.get("path") or "/"
        # Separate path from query_string
        if "?" in path:
            raw_path, query = path.split("?", 1)
        else:
            raw_path, query = path, ""

        in_headers = envelope.get("headers") or {}
        claims = envelope.get("claims") or {}

        # Serialize claims as a header so BridgeClaimsMiddleware can pick them up.
        # Also preserve caller-provided headers.
        header_items: list[tuple[bytes, bytes]] = []
        for k, v in in_headers.items():
            header_items.append((k.lower().encode(), str(v).encode()))
        header_items.append((b"x-bridge-claims", json.dumps(claims).encode()))
        # ASGI requires host header for some middleware
        if not any(k == b"host" for k, _ in header_items):
            header_items.append((b"host", b"bridge.local"))

        body = envelope.get("body") or ""
        body_bytes = body.encode("utf-8") if isinstance(body, str) else bytes(body)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": raw_path,
            "raw_path": raw_path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": header_items,
            "client": ("bridge", 0),
            "server": ("bridge.local", 443),
        }
        return scope, body_bytes

    async def _invoke_asgi(self, scope: dict, body_bytes: bytes):
        """Run a single request through the Django ASGI app, collect response."""
        sent_body = False

        async def receive():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {
                    "type": "http.request",
                    "body": body_bytes,
                    "more_body": False,
                }
            # No further body; asyncio park
            await asyncio.sleep(3600)

        response = {"status": 500, "headers": [], "body": bytearray()}

        async def send(message):
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                response["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                if message.get("body"):
                    response["body"].extend(message["body"])

        await self.asgi_app(scope, receive, send)
        return response["status"], response["headers"], bytes(response["body"])


def client_from_env() -> BridgeClient:
    return BridgeClient(
        endpoint=os.environ["BRIDGE_WS_ENDPOINT"],
        backend_secret=os.environ["BRIDGE_BACKEND_SECRET"],
    )
