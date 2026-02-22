# # chat/views.py
#
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.contrib import messages
# from django.utils import timezone
# from django.http import JsonResponse
# from django.contrib.auth.models import User
# from .models import Conversation, Message
# from .redaction import redact_text
#
#
# # ----------------------------
# # Unified Inbox + Chat view
# # ----------------------------
# @login_required
# def chat_inbox(request, conversation_id=None, user_id=None):
#     user = request.user
#     conversation = None
#
#     # ----------------------------
#     # Handle starting conversation via user_id
#     # ----------------------------
#     if user_id:
#         if user.id == int(user_id):
#             messages.error(request, "You cannot start a conversation with yourself.")
#             return redirect("chat_inbox")
#         other_user = get_object_or_404(User, id=user_id)
#         conversation = Conversation.objects.filter(participants=user).filter(participants=other_user).first()
#         if not conversation:
#             conversation = Conversation.objects.create()
#             conversation.participants.add(user, other_user)
#             conversation.save()
#         return redirect("chat_inbox_active", conversation_id=conversation.id)
#
#     # ----------------------------
#     # Get conversation if conversation_id provided
#     # ----------------------------
#     if conversation_id:
#         conversation = get_object_or_404(Conversation, id=conversation_id)
#         if not conversation.participants.filter(id=user.id).exists():
#             messages.error(request, "You are not a participant of this conversation.")
#             return redirect("chat_inbox")
#
#     # ----------------------------
#     # Handle sending a message
#     # ----------------------------
#     if request.method == "POST" and conversation:
#         text = request.POST.get("message", "").strip()
#         if text:
#             redacted_text, _ = redact_text(text)
#             msg = Message(conversation=conversation, sender=user)
#             msg.set_content(text)                   # store original encrypted
#             msg.set_redacted_content(redacted_text) # store redacted
#             msg.save()
#             conversation.updated_at = timezone.now()
#             conversation.save()
#             return redirect("chat_inbox_active", conversation_id=conversation.id)
#
#     # ----------------------------
#     # Load inbox list
#     # ----------------------------
#     query = request.GET.get("q", "").strip()
#     search_results = []
#     if query:
#         search_results = User.objects.filter(username__icontains=query).exclude(id=user.id)
#
#     conversations = user.conversations.all().order_by("-updated_at")
#     inbox_data = []
#     for convo in conversations:
#         last_msg = convo.messages.order_by("-created_at").first()
#         inbox_data.append({
#             "conversation": convo,
#             "last_message": last_msg.get_redacted_content() if last_msg else "[No messages yet]",
#             "last_time": last_msg.created_at if last_msg else convo.created_at
#         })
#
#     # ----------------------------
#     # Load active conversation messages
#     # ----------------------------
#     messages_list = []
#     participants = []
#     if conversation:
#         messages_list = conversation.messages.order_by("created_at")
#         # Ensure all messages are redacted (legacy messages)
#         for msg in messages_list:
#             if not msg.get_redacted_content() or msg.get_redacted_content() == "[REDACTED]":
#                 redacted_text, _ = redact_text(msg.get_content())
#                 msg.set_redacted_content(redacted_text)
#                 msg.save()
#         participants = conversation.participants.exclude(id=user.id)
#
#     return render(request, "chat/inbox.html", {
#         "inbox_data": inbox_data,
#         "search_results": search_results,
#         "query": query,
#         "conversation": conversation,
#         "messages": messages_list,
#         "participants": participants,
#         "user": user,
#     })
#
#
# # ----------------------------
# # Live search for users
# # ----------------------------
# @login_required
# def user_search(request):
#     query = request.GET.get("q", "").strip()
#     results = []
#     if query:
#         users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]
#         results = [{"id": u.id, "username": u.username} for u in users]
#     return JsonResponse({"results": results})
#
#
# # ----------------------------
# # JSON endpoint for live chat updates
# # ----------------------------
# @login_required
# def chat_room_json(request, conversation_id):
#     user = request.user
#     conversation = get_object_or_404(Conversation, id=conversation_id)
#     if not conversation.participants.filter(id=user.id).exists():
#         return JsonResponse({"error": "Not a participant"}, status=403)
#
#     messages_list = []
#     for msg in conversation.messages.order_by("created_at"):
#         if not msg.get_redacted_content() or msg.get_redacted_content() == "[REDACTED]":
#             redacted_text, _ = redact_text(msg.get_content())
#             msg.set_redacted_content(redacted_text)
#             msg.save()
#
#         messages_list.append({
#             "id": msg.id,
#             "sender": msg.sender.username,
#             "redacted_content": msg.get_redacted_content(),
#             "created_at": msg.created_at.strftime("%H:%M"),
#             "mine": msg.sender == user,
#         })
#     return JsonResponse({"messages": messages_list})
#
#
# # ----------------------------
# # Inbox JSON endpoint for live updates
# # ----------------------------
# @login_required
# def inbox_json(request):
#     user = request.user
#     conversations = user.conversations.all().order_by('-updated_at')
#
#     inbox_data = []
#     for convo in conversations:
#         last_msg = convo.messages.order_by('-created_at').first()
#         if last_msg:
#             redacted_text, _ = redact_text(last_msg.get_content())
#         else:
#             redacted_text = "[No messages yet]"
#
#         participants = [p.username for p in convo.participants.exclude(id=user.id)]
#         inbox_data.append({
#             "conversation_id": convo.id,
#             "participants": participants,
#             "last_message": redacted_text,
#             "last_time": last_msg.created_at.strftime("%H:%M") if last_msg else convo.created_at.strftime("%H:%M"),
#         })
#
#     return JsonResponse({"inbox_data": inbox_data})

# chat/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import Conversation, Message
from .redaction import redact_text


# ----------------------------
# Unified Inbox + Chat view
# ----------------------------
@login_required
def chat_inbox(request, conversation_id=None, user_id=None):
    user = request.user
    conversation = None

    # ----------------------------
    # Handle starting conversation via user_id
    # ----------------------------
    if user_id:
        if user.id == int(user_id):
            messages.error(request, "You cannot start a conversation with yourself.")
            return redirect("chat_inbox")
        other_user = get_object_or_404(User, id=user_id)
        conversation = Conversation.objects.filter(participants=user).filter(participants=other_user).first()
        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(user, other_user)
            conversation.save()
        # redirect to inbox with this conversation active
        return redirect("chat_inbox_active", conversation_id=conversation.id)

    # ----------------------------
    # Get conversation if conversation_id provided
    # ----------------------------
    if conversation_id:
        conversation = get_object_or_404(Conversation, id=conversation_id)
        if not conversation.participants.filter(id=user.id).exists():
            messages.error(request, "You are not a participant of this conversation.")
            return redirect("chat_inbox")

    # ----------------------------
    # Handle sending a message
    # ----------------------------
    if request.method == "POST" and conversation:
        text = request.POST.get("message", "").strip()
        if text:
            redacted_text, _ = redact_text(text)
            msg = Message(conversation=conversation, sender=user)
            msg.set_content(text)                   # store original encrypted
            msg.set_redacted_content(redacted_text) # store redacted
            msg.save()
            conversation.updated_at = timezone.now()
            conversation.save()
            # redirect to same conversation to avoid duplicate POST
            return redirect("chat_inbox_active", conversation_id=conversation.id)

    # ----------------------------
    # Load inbox list
    # ----------------------------
    query = request.GET.get("q", "").strip()
    search_results = []
    if query:
        search_results = User.objects.filter(username__icontains=query).exclude(id=user.id)

    conversations = user.conversations.all().order_by("-updated_at")
    inbox_data = []
    for convo in conversations:
        last_msg = convo.messages.order_by("-created_at").first()
        inbox_data.append({
            "conversation": convo,
            "last_message": last_msg.get_redacted_content() if last_msg else "[No messages yet]",
            "last_time": last_msg.created_at if last_msg else convo.created_at
        })

    # ----------------------------
    # Load active conversation messages
    # ----------------------------
    messages_list = []
    participants = []
    if conversation:
        messages_list = conversation.messages.order_by("created_at")
        # Ensure all messages are redacted (legacy messages)
        for msg in messages_list:
            if not msg.get_redacted_content() or msg.get_redacted_content() == "[REDACTED]":
                redacted_text, _ = redact_text(msg.get_content())
                msg.set_redacted_content(redacted_text)
                msg.save()
        participants = conversation.participants.exclude(id=user.id)

    # ----------------------------
    # Render template
    # ----------------------------
    return render(request, "chat/inbox.html", {
        "inbox_data": inbox_data,
        "search_results": search_results,
        "query": query,
        "active_convo": conversation,   # rename for template JS consistency
        "messages": messages_list,
        "participants": participants,
        "user": user,
    })


# ----------------------------
# Live search for users
# ----------------------------
@login_required
def user_search(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        users = User.objects.filter(username__icontains=query).exclude(id=request.user.id)[:10]
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
        if not msg.get_redacted_content() or msg.get_redacted_content() == "[REDACTED]":
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


# ----------------------------
# Inbox JSON endpoint for live updates
# ----------------------------
@login_required
def inbox_json(request):
    user = request.user
    conversations = user.conversations.all().order_by('-updated_at')

    inbox_data = []
    for convo in conversations:
        last_msg = convo.messages.order_by('-created_at').first()
        if last_msg:
            redacted_text, _ = redact_text(last_msg.get_content())
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