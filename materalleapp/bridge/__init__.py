"""
Materalle-2 V2 bridge.

Outbound WebSocket client that connects to the AWS API Gateway WebSocket bridge
and dispatches incoming request envelopes to the local Django ASGI application.

Components:
- ``user``       — lightweight BridgeUser object attached to request.user
- ``middleware`` — reads X-Bridge-Claims header and populates request.user
- ``client``     — asyncio WebSocket client + ASGI dispatcher
"""
