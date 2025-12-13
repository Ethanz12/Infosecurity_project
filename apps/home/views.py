from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import logging
from django.db import connection, DatabaseError

# Setup logger
logger = logging.getLogger(__name__)


def index(request):
    return render(request, "home/index.html")



def register_view(request):
    if request.method == "POST":
        # Normalize input to prevent duplicates like Admin/admin
        username = request.POST.get("username", "").strip().lower()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # Basic validation
        if not all([username, email, password, password2]):
            messages.error(request, "All fields are required.")
            return redirect("register")

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        try:
            # Prevent username & email enumeration
            if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                messages.error(request, "Registration failed. Please try different credentials.")
                return redirect("register")

            # Enforce strong passwords (Django validators)
            validate_password(password)

            # Create user securely (password is hashed)
            User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")

        except ValidationError as e:
            # Password policy error (safe to show)
            messages.error(request, e.messages[0])
            return redirect("register")

        except DatabaseError as e:
            logger.error(f"Database error during registration: {e}")
            messages.error(request, "A database error occurred. Please try again later.")
            return redirect("register")

        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
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
            # Generic error prevents user enumeration
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    return render(request, "register/login.html")



def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")



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
