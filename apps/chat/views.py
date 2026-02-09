# chat/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import Conversation, Message, SensitivePattern
from .redaction import redact_text  # ✅ new import
from django.contrib.auth.decorators import login_required

# ----------------------------
# Inbox view: list all conversations + search for new chat
# ----------------------------
@login_required
def chat_inbox(request):
    user = request.user

    # --- Search functionality ---
    query = request.GET.get("q", "")
    search_results = []
    if query:
        search_results = User.objects.filter(username__icontains=query).exclude(id=user.id)

    # --- Existing conversations ---
    conversations = user.conversations.all().order_by("-updated_at")
    inbox_data = []
    for convo in conversations:
        last_msg = convo.messages.order_by("-created_at").first()
        inbox_data.append({
            "conversation": convo,
            "last_message": last_msg.get_redacted_content() if last_msg else "[No messages yet]",
            "last_time": last_msg.created_at if last_msg else convo.created_at
        })

    return render(request, "chat/inbox.html", {
        "inbox_data": inbox_data,
        "search_results": search_results,
        "query": query,
    })


# ----------------------------
# Chat room view
# ----------------------------
@login_required
def chat_room(request, conversation_id=None, user_id=None):
    """
    Handles:
    - Viewing a conversation
    - Sending a message
    - Starting a new conversation if user_id is provided
    """
    user = request.user
    conversation = None

    # If conversation_id is provided, get it
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id)

        if not conversation.participants.filter(id=user.id).exists():
            messages.error(request, "You are not a participant of this conversation.")
            return redirect("chat_inbox")

    # If starting with a user_id, create or get conversation
    elif user_id:
        if user.id == int(user_id):
            messages.error(request, "You cannot start a conversation with yourself.")
            return redirect("chat_inbox")
        other_user = get_object_or_404(User, id=user_id)
        conversation = Conversation.objects.filter(participants=user).filter(participants=other_user).first()
        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(user, other_user)
            conversation.save()

    # Handle sending a message
    if request.method == "POST" and conversation:
        text = request.POST.get("message", "").strip()
        if text:
            redacted_text, _ = redact_text(text)
            msg = Message(conversation=conversation, sender=user)
            msg.set_content(text)                 # store original encrypted
            msg.set_redacted_content(redacted_text)  # store redacted
            msg.save()
            conversation.updated_at = timezone.now()
            conversation.save()
            return redirect("chat_room", conversation_id=conversation.id)

    # Show messages
    messages_list = conversation.messages.order_by("created_at") if conversation else []
    # Ensure all messages are redacted (legacy messages)
    for msg in messages_list:
        if not msg.get_redacted_content():
            redacted_text, _ = redact_text(msg.get_content())
            msg.set_redacted_content(redacted_text)
            msg.save()

    participants = conversation.participants.exclude(id=user.id) if conversation else []

    return render(request, "chat/room.html", {
        "conversation": conversation,
        "messages": messages_list,
        "participants": participants,
    })


# ----------------------------
# Live search for users
# ----------------------------
@login_required
def user_search(request):
    query = request.GET.get("q", "").strip()
    results = []

    if query:
        users = User.objects.filter(
            Q(username__icontains=query)
        ).exclude(id=request.user.id)[:10]

        results = [{"id": u.id, "username": u.username} for u in users]

    return JsonResponse({"results": results})


# ----------------------------
# JSON endpoint for live chat updates
# ----------------------------
@login_required
def chat_room_json(request, conversation_id):
    user = request.user
    conversation = get_object_or_404(Conversation, id=conversation_id)

    if not conversation.participants.filter(id=user.id).exists():
        return JsonResponse({"error": "Not a participant"}, status=403)

    messages_list = []
    for msg in conversation.messages.order_by("created_at"):
        # Auto-redact if empty (legacy messages)
        if not msg.get_redacted_content():
            redacted_text, _ = redact_text(msg.get_content())
            msg.set_redacted_content(redacted_text)
            msg.save()

        messages_list.append({
            "id": msg.id,
            "sender": msg.sender.username,
            "redacted_content": msg.get_redacted_content(),
            "created_at": msg.created_at.strftime("%H:%M"),
            "mine": msg.sender == user,
        })

    return JsonResponse({"messages": messages_list})

@login_required
def inbox_json(request):
    """
    Returns JSON of user's inbox for live updates, with automatic redaction applied.
    """
    user = request.user
    conversations = user.conversations.all().order_by('-updated_at')

    inbox_data = []
    for convo in conversations:
        last_msg = convo.messages.order_by('-created_at').first()

        # Redact the last message
        if last_msg:
            redacted_text = redact_text(last_msg.get_content())
        else:
            redacted_text = "[No messages yet]"

        participants = [p.username for p in convo.participants.exclude(id=user.id)]
        inbox_data.append({
            "conversation_id": convo.id,
            "participants": participants,
            "last_message": redacted_text,
            "last_time": last_msg.created_at.strftime("%H:%M") if last_msg else convo.created_at.strftime("%H:%M"),
        })

    return JsonResponse({"inbox_data": inbox_data})
