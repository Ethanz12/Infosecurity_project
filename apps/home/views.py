from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
import logging
from django.db import connection, DatabaseError

# Setup logger
logger = logging.getLogger(__name__)

# -------------------------------
# Home Page
# -------------------------------
def index(request):
    return render(request, "home/index.html")


# -------------------------------
# Register Page
# -------------------------------
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # Validate input
        if not username or not email or not password or not password2:
            messages.error(request, "All fields are required.")
            return redirect("register")

        if password != password2:
            messages.error(request, "Passwords do not match!")
            return redirect("register")

        try:
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already taken!")
                return redirect("register")

            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
            messages.success(request, "Account created successfully! Please login.")
            return redirect("login")

        except DatabaseError as e:
            logger.error(f"Database error during registration: {e}")
            messages.error(request, "A database error occurred. Please try again later.")
            return redirect("register")

        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
            messages.error(request, "An unexpected error occurred. Please try again later.")
            return redirect("register")

    return render(request, "register/register.html")


# -------------------------------
# Login Page
# -------------------------------
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
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


# -------------------------------
# Logout
# -------------------------------
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")


# -------------------------------
# Test DB Connection
# -------------------------------
def test_db_connection(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                logger.info("MySQL connection successful")
                return HttpResponse("MySQL connection successful")
            else:
                return HttpResponse("MySQL returned unexpected result")
    except Exception as e:
        logger.error(f"MySQL connection failed: {e}")
        return HttpResponse(f"MySQL connection failed: {e}", status=500)
