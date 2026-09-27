from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from website.models import LearningSession
from .session_serializers import SessionListSerializer, SessionDetailSerializer
from .response import api_response


class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = LearningSession.objects.filter(user=request.user).order_by("-start_time")
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 20))
        total = sessions.count()
        start = (page - 1) * per_page
        sessions = sessions[start : start + per_page]
        serializer = SessionListSerializer(sessions, many=True)
        return api_response(
            data=serializer.data,
            meta={"page": page, "per_page": per_page, "total": total},
        )


class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            session = LearningSession.objects.get(pk=pk, user=request.user)
        except LearningSession.DoesNotExist:
            return api_response(
                message="Session not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        serializer = SessionDetailSerializer(session)
        return api_response(data=serializer.data)