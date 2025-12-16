from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('test-db/', views.test_db_connection, name='test_db'),
    path("staff/", views.staff_page, name="staff_page"),
]

