"""
ReadOnlyModeMiddleware — when ``READ_ONLY_MODE=true`` is set, reject any
request that would mutate state. Used by the hosted Django fallback so the
hosted instance can never diverge from a daycare's local DB.

Safe methods (GET/HEAD/OPTIONS) always pass. Auth-related paths are
exempted so users can still sign in against the hosted fallback.
"""
from __future__ import annotations

import os

from django.http import JsonResponse

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PREFIXES = ("/api/v1/auth/", "/api/v1/agents/")


class ReadOnlyModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = os.environ.get("READ_ONLY_MODE", "").lower() in ("1", "true", "yes")

    def __call__(self, request):
        if self.enabled and request.method not in SAFE_METHODS:
            if not any(request.path.startswith(p) for p in EXEMPT_PREFIXES):
                return JsonResponse(
                    {"status": "error", "message": "hosted fallback is read-only"},
                    status=405,
                )
        return self.get_response(request)
