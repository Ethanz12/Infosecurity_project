from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.db import connection
from django import forms
import logging
import os

from .models import CitizenProfile

logger = logging.getLogger(__name__)

HARD_ROLES = ["Citizen", "GovernmentWorker"]

# --------------------
# Helper Functions
# --------------------

def get_or_create_roles():
    for role in HARD_ROLES:
        Group.objects.get_or_create(name=role)

def create_admin_if_missing():
    admin_username = os.getenv("ADMIN_USER", "admin")
    admin_password = os.getenv("ADMIN_PASS", "adminpass")
    if not User.objects.filter(username=admin_username).exists():
        User.objects.create_superuser(
            username=admin_username,
            email="admin@example.com",
            password=admin_password
        )
        logger.info("Admin account created automatically.")

def mask_nric(nric: str):
    if not nric or len(nric) < 4:
        return ""
    return nric[0] + "****" + nric[-3:]

def mask_phone(phone: str):
    if not phone or len(phone) < 4:
        return ""
    return phone[0] + "****" + phone[-3:]

# --------------------
# Forms
# --------------------

class CitizenProfileForm(forms.Form):
    nric = forms.CharField(max_length=9, required=False)
    phone = forms.CharField(max_length=15, required=False)
    address = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False
    )

    def clean_nric(self):
        nric = self.cleaned_data.get("nric")

        if not nric:
            return nric

        # Ignore masked display value
        if "*" in nric:
            return nric

        if len(nric) != 9:
            raise forms.ValidationError(
                "NRIC must be exactly 9 characters."
            )

        return nric

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")

        if not phone:
            return phone

        # Ignore masked display value
        if "*" in phone:
            return phone

        if not phone.isdigit():
            raise forms.ValidationError(
                "Phone number must contain digits only."
            )

        if len(phone) < 8:
            raise forms.ValidationError(
                "Phone number must be at least 8 digits."
            )

        return phone

# --------------------
# Views
# --------------------

@login_required
def profile_view(request):
    profile, created = CitizenProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = CitizenProfileForm(request.POST)
        if form.is_valid():
            nric = form.cleaned_data.get("nric")
            phone = form.cleaned_data.get("phone")
            address = form.cleaned_data.get("address")

            def is_masked(value):
                return value and "*" in value

            if nric and not is_masked(nric):
                profile.set_nric(nric)  # encryption
            if phone and not is_masked(phone):
                profile.set_phone(phone)  # encryption
            if address:
                profile.set_address(address)

            # Update full name & email
            full_name = request.POST.get("full_name", "").strip()
            if full_name:
                parts = full_name.split(" ", 1)
                request.user.first_name = parts[0]
                request.user.last_name = parts[1] if len(parts) > 1 else ""
                request.user.save()

            email = request.POST.get("email", "").strip()
            if email:
                request.user.email = email
                request.user.save()

            profile.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")

        else:
            # Form has errors → mask NRIC/phone before sending to template
            raw_nric = request.POST.get("nric", "")
            raw_phone = request.POST.get("phone", "")

            context = {
                "form_data": request.POST,
                "errors": {k: v[0] for k, v in form.errors.items()},
                "user": request.user,
                "masked_nric": mask_nric(profile.get_nric() if "*" in raw_nric else raw_nric),
                "masked_phone": mask_phone(profile.get_phone() if "*" in raw_phone else raw_phone),
            }
            return render(request, "home/profile.html", context)

    else:
        # GET request - FIX APPLIED HERE
        context = {
            "form_data": {
                "full_name": request.user.get_full_name(),
                "email": request.user.email,
                # The fix: Apply mask functions here so the template receives masked data
                "nric": mask_nric(profile.get_nric()),
                "phone": mask_phone(profile.get_phone()),
                "address": profile.get_address(),
            },
            "errors": {},
            "user": request.user,
            "masked_nric": mask_nric(profile.get_nric()),
            "masked_phone": mask_phone(profile.get_phone()),
        }
        return render(request, "home/profile.html", context)


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
            validate_password(password)
            get_or_create_roles()

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            citizen_group = Group.objects.get(name="Citizen")
            user.groups.add(citizen_group)

            messages.success(request, "Account created successfully.")
            return redirect("login")

        except ValidationError as e:
            messages.error(request, e.messages[0])
        except Exception as e:
            logger.error(e)
            messages.error(request, "Unexpected error occurred.")

        return redirect("register")

    return render(request, "register/register.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").lower()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("home")

        messages.error(request, "Invalid credentials.")
        return redirect("login")

    return render(request, "register/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def test_db_connection(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return HttpResponse("Database connection successful")
    except Exception:
        return HttpResponse("Database connection failed", status=500)