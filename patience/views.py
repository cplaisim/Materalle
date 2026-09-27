import re
import json
from django.shortcuts import render, redirect
from django.utils import timezone
from .forms import patienceForm
from .models import MotorCurriculum
from django.http import JsonResponse
from .agents import PatienceAgent
from enroll.models import Student, Child, StudentRating
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from agent.models import Conversation, Message
from materalleapp.agent_base import get_anthropic_response

PATIENCE_SYSTEM_PROMPT = PatienceAgent().get_system_prompt()

MOTOR_ACTIVITY_TYPE_MAP = {
    'FINE': 'FINE',
    'GROSS': 'GROSS',
    'HAND_EYE': 'HAND_EYE',
    'BALANCE': 'BALANCE',
    'SENSORY': 'SENSORY',
}

MOTOR_VALID_AGE_RANGES = ['0-1', '1-2', '2-3', '3-4', '4-5']


def _parse_activity_field(text, field_name):
    """Extract a field value from structured LLM response like **Field:** value"""
    pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?=\n\*\*|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ''


def _build_patience_messages(conversation, user_message):
    """Build the messages list for the Anthropic API from conversation history."""
    messages = []
    for msg in conversation.message_set.order_by('timestamp'):
        role = "user" if msg.is_user else "assistant"
        messages.append({"role": role, "content": msg.content})
    return messages

@login_required
def index(request):
    conversations = Conversation.objects.filter(user=request.user).order_by('-created_at')
    students = Child.objects.all()

    # Build per-child rating summaries for Patience activities
    patience_ct = ContentType.objects.get_for_model(MotorCurriculum)
    children_data = []
    for child in students:
        ratings = StudentRating.objects.filter(child=child, content_type=patience_ct)
        likes = ratings.filter(rating__gte=3).count()
        normals = ratings.filter(rating=2).count()
        dislikes = ratings.filter(rating__lte=1).count()
        children_data.append({
            'child': child,
            'likes': likes,
            'normals': normals,
            'dislikes': dislikes,
            'total_ratings': ratings.count(),
        })

    return render(request, 'patience/index.html', {
        'conversations': conversations,
        'students': students,
        'children_data': children_data,
        'page': 'patience',
    })


@login_required
def chat_view(request, conversation_id=None):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            conversation_id = data.get('conversation_id')

            if conversation_id:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            else:
                conversation = Conversation.objects.create(
                    user=request.user,
                    title="Patience Chat"
                )

            Message.objects.create(
                conversation=conversation,
                content=user_message,
                is_user=True
            )

            messages_for_claude = _build_patience_messages(conversation, user_message)
            from sage.views import get_rag_context
            rag = get_rag_context(request.user)
            system = PATIENCE_SYSTEM_PROMPT + rag
            response_text = get_anthropic_response(messages=messages_for_claude, system_prompt=system)

            Message.objects.create(
                conversation=conversation,
                content=response_text,
                is_user=False
            )

            return JsonResponse({
                'message': response_text,
                'conversation_id': conversation.id
            })

        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)

    conversations = Conversation.objects.filter(user=request.user).order_by('-created_at')
    students = Child.objects.all()
    return render(request, 'patience/chat.html', {
        'conversations': conversations,
        'students': students,
    })

@login_required
def get_conversation(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')

        return JsonResponse({
            'messages': [{
                'content': msg.content,
                'is_user': msg.is_user,
                'timestamp': msg.created_at.isoformat()
            } for msg in messages]
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)


@login_required
def delete_conversation(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        conversation.delete()
        return JsonResponse({'success': True})
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def patience_chat(request):
    students = Child.objects.all()
    return render(request, 'patience/chat.html', {'students': students})

@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            conversation_id = data.get('conversation_id')

            if conversation_id:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
            else:
                conversation = Conversation.objects.create(
                    user=request.user,
                    title="Patience Chat"
                )

            Message.objects.create(
                conversation=conversation,
                content=user_message,
                is_user=True
            )

            messages_for_claude = _build_patience_messages(conversation, user_message)
            from sage.views import get_rag_context
            rag = get_rag_context(request.user)
            system = PATIENCE_SYSTEM_PROMPT + rag
            response_text = get_anthropic_response(messages=messages_for_claude, system_prompt=system)

            Message.objects.create(
                conversation=conversation,
                content=response_text,
                is_user=False
            )

            # Parse structured activity fields from the response
            title = _parse_activity_field(response_text, 'Title')
            activity_type_raw = _parse_activity_field(response_text, 'Activity Type').upper().strip()
            age_range = _parse_activity_field(response_text, 'Age Range').strip()
            description = _parse_activity_field(response_text, 'Description')
            developmental_goal = _parse_activity_field(response_text, 'Developmental Goal')
            materials = _parse_activity_field(response_text, 'Materials')
            safety_notes = _parse_activity_field(response_text, 'Safety Notes')
            duration_str = _parse_activity_field(response_text, 'Duration')

            entry = None
            if title:
                activity_type = MOTOR_ACTIVITY_TYPE_MAP.get(activity_type_raw, 'GROSS')
                if age_range not in MOTOR_VALID_AGE_RANGES:
                    age_range = '2-3'
                duration = int(re.search(r'\d+', duration_str).group()) if duration_str and re.search(r'\d+', duration_str) else 15

                entry = MotorCurriculum.objects.create(
                    title=title[:200],
                    activity_type=activity_type,
                    age_range=age_range,
                    description=description,
                    developmental_goal=developmental_goal,
                    materials=materials,
                    safety_notes=safety_notes,
                    duration_minutes=duration,
                    created_by=request.user,
                )

            return JsonResponse({
                'message': response_text,
                'conversation_id': conversation.id,
                'entry_id': entry.pk if entry else None,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required
def handle_interaction(request):
    return render(request, 'patience/chat.html')
