from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
import logging
from django.db import connection, DatabaseError
import os  # ← Needed for os.getenv

# Setup logger
logger = logging.getLogger(__name__)

HARD_ROLES = ["Citizen", "GovernmentWorker"]

def get_or_create_roles():
    """Ensure roles exist, create if missing"""
    for role in HARD_ROLES:
        Group.objects.get_or_create(name=role)

def create_admin_if_missing():
    """Create admin user from environment variables if not exists"""
    admin_username = os.getenv("ADMIN_USER", "admin")
    admin_password = os.getenv("ADMIN_PASS", "adminpass")
    if not User.objects.filter(username=admin_username).exists():
        User.objects.create_superuser(username=admin_username, email="admin@example.com", password=admin_password)
        logger.info(f"Admin user '{admin_username}' created automatically.")

# ====================
# Views
# ====================

def index(request):
    return render(request, "home/index.html")

def register_view(request):
    create_admin_if_missing()  # Ensure admin exists before registering normal users

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        if not all([username, email, password, password2]):
            messages.error(request, "All fields are required.")
            return redirect("register")

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        try:
            if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                messages.error(request, "Registration failed. Please try different credentials.")
                return redirect("register")

            validate_password(password)
            get_or_create_roles()

            user = User.objects.create_user(username=username, email=email, password=password)

            # Auto-assign Citizen role for normal users (skip admin)
            admin_username = os.getenv("ADMIN_USER", "admin")
            if username != admin_username:
                citizen_group = Group.objects.get(name="Citizen")
                user.groups.add(citizen_group)

            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")

        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect("register")
        except DatabaseError as e:
            logger.error(f"Database error during registration: {e}")
            messages.error(request, "A database error occurred. Please try again later.")
            return redirect("register")
        except Exception:
            logger.exception("Unexpected error during registration")
            messages.error(request, "An unexpected error occurred. Please try again later.")
            return redirect("register")

    return render(request, "register/register.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    return render(request, "register/login.html")

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")

@login_required
def test_db_connection(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                logger.info("Database connection successful")
                return HttpResponse("Database connection successful")
            else:
                return HttpResponse("Database returned unexpected result")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return HttpResponse("Database connection failed", status=500)
