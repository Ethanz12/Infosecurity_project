# chat/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # ----------------------------
    # Unified Inbox + Chat View
    # ----------------------------
    path('inbox/', views.chat_inbox, name='chat_inbox'),                            # Main inbox page
    path('inbox/<int:conversation_id>/', views.chat_inbox, name='chat_inbox_active'),  # Open specific conversation
    path('start/<int:user_id>/', views.chat_inbox, name='chat_start'),              # Start new conversation with user

    # ----------------------------
    # Live User Search
    # ----------------------------
    path('user_search/', views.user_search, name='user_search'),

    # ----------------------------
    # JSON Endpoints for AJAX
    # ----------------------------
    path('inbox/json/', views.inbox_json, name='inbox_json'),                       # Inbox live updates
    path('room/json/<int:conversation_id>/', views.chat_room_json, name='chat_room_json'),  # Chat messages live updates
]