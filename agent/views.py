from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Conversation, Message
from materalleapp.agent_base import get_anthropic_response

# Create your views here.

@login_required
def chat_view(request, conversation_id=None):
    if conversation_id:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = conversation.message_set.all()
    else:
        conversation = None
        messages = []
    
    return render(request, 'agent/chat.html', {
        'conversation': conversation,
        'messages': messages,
    })
    
@login_required
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    user_message = request.POST.get('message')
    conversation_id = request.POST.get('conversation_id')
    
    if not conversation_id:
        # Create new conversation
        conversation = Conversation.objects.create(
            user=request.user,
            title=user_message[:50]  # Use first 50 chars as title
        )
    else:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user) # Added user check
    
    # Save user message
    Message.objects.create(
        conversation=conversation,
        content=user_message,
        is_user=True
    )
    
    # Get conversation history
    history = conversation.message_set.order_by('timestamp') # Order chronologically for API
    messages_for_claude = []
    # How should system prompt be handled? Assume generic for now.
    # messages_for_claude.append({"role": "system", "content": "You are a helpful assistant."}) 
    for msg in history:
        role = "user" if msg.is_user else "assistant"
        messages_for_claude.append({"role": role, "content": msg.content})
    
    # *** Integration Point: Replace direct API call with helper function call ***
    try:
        # --- Old Direct Call (to be replaced) ---
        # response = client.messages.create(
        #     model="claude-3-opus-20240229",
        #     max_tokens=1024,
        #     messages=messages_for_claude
        # )
        # assistant_text = response.content[0].text if response.content else "Error: No response content."
        # --- New Call using Helper --- 
        from sage.views import get_rag_context
        rag = get_rag_context(request.user)
        system = rag if rag else None
        assistant_text = get_anthropic_response(messages=messages_for_claude, system_prompt=system)
        
        # Save Claude's response
        assistant_message_obj = Message.objects.create(
            conversation=conversation,
            content=assistant_text,
            is_user=False
        )
        
        return JsonResponse({
            'message': assistant_message_obj.content,
            'conversation_id': conversation.id
        })
        
    except Exception as e:
        # The helper function raises errors, so we catch them here.
        return JsonResponse({'error': str(e)}, status=500)