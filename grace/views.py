import re
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from .models import Conversation, Message
from enroll.models import Child, StudentRating
from materalleapp.agent_base import get_agent_response
from .models import SocialCurriculum
from .agents import GraceAgent

GRACE_SYSTEM_PROMPT = GraceAgent().get_system_prompt()


SOCIAL_ACTIVITY_TYPE_MAP = {
    'EMOTIONAL': 'EMOTIONAL',
    'SHARING': 'SHARING',
    'EMPATHY': 'EMPATHY',
    'CONFLICT': 'CONFLICT',
    'SELF_REG': 'SELF_REG',
    'SOCIAL_PLAY': 'SOCIAL_PLAY',
    'COMMUNICATION': 'COMMUNICATION',
}

SOCIAL_VALID_AGE_RANGES = ['0-1', '1-2', '2-3', '3-4', '4-5']


def _parse_activity_field(text, field_name):
    """Extract a field value from structured LLM response like **Field:** value"""
    pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?=\n\*\*|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ''

@login_required
def index(request):
    conversations = Conversation.objects.filter(user=request.user).order_by('-created_at')
    students = Child.objects.all()
    latest_activity = SocialCurriculum.objects.order_by('-created_at').first()

    # Build per-child rating summaries for Grace activities
    grace_ct = ContentType.objects.get_for_model(SocialCurriculum)
    children_data = []
    for child in students:
        ratings = StudentRating.objects.filter(child=child, content_type=grace_ct)
        likes = ratings.filter(rating__gte=3).count()
        normals = ratings.filter(rating=2).count()
        dislikes = ratings.filter(rating__lte=1).count()
        recent = SocialCurriculum.objects.order_by('-created_at')[:3]
        children_data.append({
            'child': child,
            'likes': likes,
            'normals': normals,
            'dislikes': dislikes,
            'total_ratings': ratings.count(),
            'recent_activities': list(recent.values('id', 'title', 'activity_type')),
        })

    return render(request, 'grace/index.html', {
        'conversations': conversations,
        'conversation': None,
        'students': students,
        'children_data': children_data,
        'current_activity_id': latest_activity.pk if latest_activity else '',
        'children_data_json': json.dumps([{
            'child_id': d['child'].child_id,
            'child_name': d['child'].child_name,
            'date_of_birth': str(d['child'].date_of_birth) if d['child'].date_of_birth else '',
            'is_checked_in': d['child'].is_checked_in,
            'likes': d['likes'],
            'normals': d['normals'],
            'dislikes': d['dislikes'],
            'total_ratings': d['total_ratings'],
            'recent_activities': d['recent_activities'],
        } for d in children_data]),
        'page': 'grace',
    })

@login_required
def chat_view(request, conversation_id=None):
    conversations = Conversation.objects.filter(user=request.user).order_by('-created_at')
    students = Child.objects.all()

    if conversation_id:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = conversation.grace_messages.all()
    else:
        conversation = None
        messages = []

    return render(request, 'grace/chat.html', {
        'conversation': conversation,
        'conversations': conversations,
        'messages': messages,
        'students': students,
    })

@login_required
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    user_message = request.POST.get('message')
    conversation_id = request.POST.get('conversation_id')

    if not conversation_id:
        conversation = Conversation.objects.create(
            user=request.user,
            title=user_message[:50]
        )
    else:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)

    Message.objects.create(
        conversation=conversation,
        content=user_message,
        is_user=True
    )

    history = conversation.grace_messages.order_by('timestamp')
    messages_for_claude = []
    for msg in history:
        role = "user" if msg.is_user else "assistant"
        messages_for_claude.append({"role": role, "content": msg.content})

    try:
        from sage.views import get_rag_context
        rag = get_rag_context(request.user)
        system = GRACE_SYSTEM_PROMPT + rag
        assistant_text, fallback_used = get_agent_response('grace', messages_for_claude, system)

        assistant_message_obj = Message.objects.create(
            conversation=conversation,
            content=assistant_text,
            is_user=False
        )

        # Parse structured activity fields from the response
        title = _parse_activity_field(assistant_text, 'Title')
        activity_type_raw = _parse_activity_field(assistant_text, 'Activity Type').upper().strip()
        age_range = _parse_activity_field(assistant_text, 'Age Range').strip()
        description = _parse_activity_field(assistant_text, 'Description')
        developmental_goal = _parse_activity_field(assistant_text, 'Developmental Goal')
        materials = _parse_activity_field(assistant_text, 'Materials')
        duration_str = _parse_activity_field(assistant_text, 'Duration')
        group_size = _parse_activity_field(assistant_text, 'Group Size')

        entry = None
        if title:
            activity_type = SOCIAL_ACTIVITY_TYPE_MAP.get(activity_type_raw, 'SOCIAL_PLAY')
            if age_range not in SOCIAL_VALID_AGE_RANGES:
                age_range = '2-3'
            duration = int(re.search(r'\d+', duration_str).group()) if duration_str and re.search(r'\d+', duration_str) else 15

            entry = SocialCurriculum.objects.create(
                title=title[:200],
                activity_type=activity_type,
                age_range=age_range,
                description=description,
                developmental_goal=developmental_goal,
                materials=materials,
                duration_minutes=duration,
                group_size=group_size[:50] if group_size else '',
                created_by=request.user,
            )

        return JsonResponse({
            'message': assistant_message_obj.content,
            'conversation_id': conversation.id,
            'entry_id': entry.pk if entry else None,
            'fallback': fallback_used,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_conversation(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = conversation.grace_messages.all()

        return JsonResponse({
            'messages': [
                {
                    'content': msg.content,
                    'is_user': msg.is_user,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in messages
            ]
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def handle_interaction(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        import json
        data = json.loads(request.body)
        action_type = data.get('action_type')
        details = data.get('details')

        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["DELETE"])
def delete_conversation(request, conversation_id):
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id, user=request.user)
        conversation.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
