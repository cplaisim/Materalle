from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .response import api_response
from materalleapp.agent_base import get_anthropic_response, get_llm_backend


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return api_response(data={"status": "healthy"}, message="Materalle API v1")


class OllamaTestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            message = request.data.get("message", "Hello, what is your name?")
            backend = get_llm_backend()

            response_text = get_anthropic_response(
                messages=[{"role": "user", "content": message}],
                system_prompt="You are a helpful AI assistant. Keep responses brief."
            )

            return Response({
                "success": True,
                "backend": backend,
                "user_message": message,
                "assistant_response": response_text
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e),
                "backend": get_llm_backend()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)