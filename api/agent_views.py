import asyncio

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from grace.agents import GraceAgent
from patience.agents import PatienceAgent
from sage.agents import SageAgent
from grace.models import Conversation, Message
from website.models import LearningSession

from .agent_serializers import ChatRequestSerializer
from .response import api_response


class AgentChatView(APIView):
    """Base chat view for AI agent interaction."""
    permission_classes = [IsAuthenticated]
    agent_class = None
    agent_name = None

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                message="Validation failed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user_message = serializer.validated_data["message"]
        session_id = serializer.validated_data.get("session_id")

        # Get or create a learning session
        if session_id:
            try:
                session = LearningSession.objects.get(pk=session_id, user=request.user)
            except LearningSession.DoesNotExist:
                return api_response(
                    message="Session not found.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
        else:
            session = LearningSession.objects.create(user=request.user)

        # Get or create conversation for this session/agent
        conversation, _ = Conversation.objects.get_or_create(
            user=request.user,
            title=f"{self.agent_name} - Session {session.pk}",
            defaults={"title": f"{self.agent_name} - Session {session.pk}"},
        )

        # Save user message
        user_msg = Message.objects.create(
            conversation=conversation,
            content=user_message,
            is_user=True,
        )

        # Build context from conversation history
        history = Message.objects.filter(conversation=conversation).order_by("timestamp")
        context = [
            {"role": "user" if m.is_user else "assistant", "content": m.content}
            for m in history
            if m.pk != user_msg.pk  # exclude current message, agent adds it
        ]

        # Get agent response
        agent = self.agent_class()
        loop = asyncio.new_event_loop()
        try:
            response_text = loop.run_until_complete(
                agent.get_response(user_message, context=context)
            )
        finally:
            loop.close()

        # Save assistant message
        assistant_msg = Message.objects.create(
            conversation=conversation,
            content=response_text,
            is_user=False,
        )

        return api_response(
            data={
                "agent": self.agent_name,
                "response": response_text,
                "session_id": session.pk,
                "message_id": assistant_msg.pk,
            },
            message="Response generated.",
        )


class GraceChatView(AgentChatView):
    agent_class = GraceAgent
    agent_name = "Grace"


class PatienceChatView(AgentChatView):
    agent_class = PatienceAgent
    agent_name = "Patience"


class SagesseChatView(AgentChatView):
    agent_class = SageAgent
    agent_name = "Sagesse"