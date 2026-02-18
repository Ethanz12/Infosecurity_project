from django.urls import path, include  # include added
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('test-db/', views.test_db_connection, name='test_db'),
    path("staff/", views.staff_page, name="staff_page"),
    path('profile/', views.profile_view, name='profile'),
    path('upload/', views.upload_file, name='upload_file'),
    path('files/', views.file_list, name='file_list'),
    path('view/<int:file_id>/', views.view_file, name='view_file'),  # NEW
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/create/', views.create_ticket, name='create_ticket'),
    path('ticket/<uuid:ticket_uuid>/', views.ticket_detail, name='ticket_detail'),
    path('logs/', views.view_logs, name='view_logs'),
    path('staff/medical/update/<int:citizen_id>/', views.update_medical_record, name='update_medical_record'),
    path('staff/dental/all/', views.dental_record_list, name='dental_record_list'),

    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('resend-2fa/', views.resend_2fa_code, name='resend_2fa'),
    path('security/settings/', views.security_settings, name='security_settings'),
    path('security/toggle-2fa/', views.toggle_2fa, name='toggle_2fa'),
    

    # ----------------------------
    # Chat integration
    # ----------------------------
    path('chat/', include('apps.chat.urls')),  # includes chat app URLs
]
