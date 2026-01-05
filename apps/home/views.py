# apps/home/views.py

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.db import connection, DatabaseError
from django import forms
import logging
import os

# Import your model
from .models import CitizenProfile

logger = logging.getLogger(__name__)

HARD_ROLES = ["Citizen", "GovernmentWorker"]

# --- HELPER FUNCTIONS ---
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

# --- FORM CLASS ---
class CitizenProfileForm(forms.Form):
    nric = forms.CharField(
        max_length=9, 
        required=False, 
        label="NRIC (Encrypted)"
    )
    phone = forms.CharField(
        max_length=15, 
        required=False, 
        label="Phone Number (Encrypted)"
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), 
        required=False, 
        label="Home Address (Encrypted)"
    )

# --- VIEWS ---

@login_required
def profile_view(request):
    """
    Secure Profile View:
    - Fetches encrypted data from DB -> Decrypts for the Form
    - Takes clean data from Form -> Encrypts for the DB
    """
    # 1. Get the profile safely (create if missing)
    profile, created = CitizenProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = CitizenProfileForm(request.POST)
        if form.is_valid():
            # Get cleartext from form
            nric_clear = form.cleaned_data['nric']
            phone_clear = form.cleaned_data['phone']
            address_clear = form.cleaned_data['address']

            # Encrypt and set to model (only if data exists)
            profile.set_nric(nric_clear)
            profile.set_phone(phone_clear)
            profile.set_address(address_clear)
            
            # Save to DB
            profile.save()
            
            messages.success(request, "Profile updated securely.")
            return redirect('profile') # Redirect prevents re-submission
    else:
        # Pre-fill form with decrypted data
        initial_data = {
            'nric': profile.get_nric(),
            'phone': profile.get_phone(),
            'address': profile.get_address()
        }
        form = CitizenProfileForm(initial=initial_data)

    return render(request, "home/profile.html", {'form': form})

@login_required
def staff_page(request):
    user = request.user
    if user.is_staff or user.groups.filter(name="GovernmentWorker").exists():
        return render(request, "staff/staff_page.html")
    return HttpResponseForbidden("403 Forbidden – Access denied")

def index(request):
    return render(request, "home/index.html")

def register_view(request):
    create_admin_if_missing()
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
                messages.error(request, "Registration failed. Try different credentials.")
                return redirect("register")

            validate_password(password)
            get_or_create_roles()

            user = User.objects.create_user(username=username, email=email, password=password)
            
            # Auto-assign Citizen role
            admin_username = os.getenv("ADMIN_USER", "admin")
            if username != admin_username:
                citizen_group = Group.objects.get(name="Citizen")
                user.groups.add(citizen_group)

            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")

        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect("register")
        except Exception as e:
            logger.error(f"Error: {e}")
            messages.error(request, "An unexpected error occurred.")
            return redirect("register")

    return render(request, "register/register.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")
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
    messages.success(request, "Logged out.")
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