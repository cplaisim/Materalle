import httpx
from django.db import connection
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from .response import api_response


class LLMSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from website.models import LLMSettings
        s = LLMSettings.get_settings()
        return api_response(data={
            "backend": s.backend,
            "anthropic_api_key_set": bool(s.anthropic_api_key),
            "ollama_base_url": s.ollama_base_url,
            "ollama_model": s.ollama_model,
            "local_api_url": s.local_api_url,
            "local_model": s.local_model,
        })

    def patch(self, request):
        from website.models import LLMSettings
        s = LLMSettings.get_settings()
        data = request.data

        allowed = ("backend", "anthropic_api_key", "ollama_base_url",
                    "ollama_model", "local_api_url", "local_model")
        updated = []
        for field in allowed:
            if field in data:
                setattr(s, field, data[field])
                updated.append(field)

        if not updated:
            return api_response(message="No fields to update", status_code=status.HTTP_400_BAD_REQUEST)

        s.save(update_fields=updated + ["updated_at"])
        return api_response(data={"backend": s.backend}, message="Settings updated")


class SystemHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        checks = {}

        # Database
        try:
            connection.ensure_connection()
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        # Django server (if we're responding, it's up)
        checks["django"] = "ok"

        # LLM backend
        from website.models import LLMSettings
        s = LLMSettings.get_settings()
        checks["llm_backend"] = s.backend
        checks["llm"] = self._check_llm(s)

        return api_response(data=checks)

    def _check_llm(self, settings):
        backend = settings.backend
        try:
            if backend == "anthropic":
                if not settings.anthropic_api_key:
                    from django.conf import settings as django_settings
                    if not getattr(django_settings, "ANTHROPIC_API_KEY", ""):
                        return "warning"
                return "ok"

            if backend == "ollama":
                url = settings.ollama_base_url or "http://localhost:12434"
                r = httpx.get(f"{url}/api/tags", timeout=3.0)
                return "ok" if r.status_code == 200 else "error"

            # OpenAI-compatible local backends
            url = settings.local_api_url or "http://localhost:1234"
            r = httpx.get(f"{url}/v1/models", timeout=3.0)
            return "ok" if r.status_code == 200 else "error"
        except Exception:
            return "error"
