# chat/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('inbox/', views.chat_inbox, name='chat_inbox'),
    path('inbox/json/', views.inbox_json, name='inbox_json'),
    path('room/<int:conversation_id>/', views.chat_room, name='chat_room'),
    path('room/start/<int:user_id>/', views.chat_room, name='chat_start'),
    path('room/json/<int:conversation_id>/', views.chat_room_json, name='chat_room_json'),  # <--- add this
    path('user_search/', views.user_search, name='user_search'),
]

