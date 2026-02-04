from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction, IntegrityError
from django import forms
import logging
import os
from django.shortcuts import get_object_or_404
from .models import Ticket

from .models import CitizenProfile

#S3 Stuff
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .models import UploadedFile
import uuid

#View Classified files
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .models import UploadedFile
from .classification import FileClassifier, FileReader 
from django.utils import timezone
import uuid
import json

# NEW IMPORTS FOR ABAC
from .models import StaffProfile, DEPARTMENTS

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
        # GET request
        context = {
            "form_data": {
                "full_name": request.user.get_full_name(),
                "email": request.user.email,
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
        nric = request.POST.get("nric", "").strip().upper()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # --- 1. Basic Empty Field Check ---
        if not all([username, email, nric, password, password2]):
            messages.error(request, "All fields are required.")
            return redirect("register")

        # --- 2. NRIC Format Validation ---
        if len(nric) != 9:
            messages.error(request, "Invalid NRIC: Must be exactly 9 characters (e.g., S1234567A).")
            return redirect("register")
        
        if nric[0] not in ['S', 'T', 'F', 'G', 'M']:
            messages.error(request, "Invalid NRIC: Must start with S, T, F, G, or M.")
            return redirect("register")

        # --- 3. Password Match ---
        if password != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        try:
            validate_password(password)
            
            # --- 4. Atomic Transaction ---
            with transaction.atomic():
                # Create User
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                # Assign Role (FIXED: use get_or_create to prevent crash)
                citizen_group, _ = Group.objects.get_or_create(name="Citizen")
                user.groups.add(citizen_group)

                # Create Profile (FIXED: use get_or_create to prevent IntegrityError)
                profile, created = CitizenProfile.objects.get_or_create(user=user)
                profile.set_nric(nric)
                profile.save()

            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")

        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect("register")

        except Exception as e:
            logger.error(f"Registration Error: {e}")
            messages.error(request, "An unexpected error occurred. Please try again.")
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
    
#S3 Stuff

@login_required
def upload_file(request):

    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']

        # Generate unique filename to prevent conflicts
        file_extension = uploaded_file.name.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"uploads/{request.user.username}/{unique_filename}"

        try:
        
            # Upload to S3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )

            s3_client.upload_fileobj(
                uploaded_file,
                settings.AWS_STORAGE_BUCKET_NAME,
                s3_key,
                ExtraArgs={'ContentType': uploaded_file.content_type}
            )

            # Save to database with classification
            file_record = UploadedFile.objects.create(
                user=request.user,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                s3_key=s3_key,
                file_type=uploaded_file.content_type
        
            )

            messages.success(request, f"File '{uploaded_file.name}' uploaded successfully!")

            return redirect('file_list')

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            messages.error(request, "Failed to upload file to cloud storage.")
            return redirect('upload_file')

        except Exception as e:
            logger.error(f"Upload error: {e}")
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('upload_file')

    return render(request, 'home/upload.html')

@login_required
def file_list(request):
    files = UploadedFile.objects.filter(user=request.user)
    return render(request, 'home/file_list.html', {'files': files})

@login_required
def download_file(request, file_id):
    try:
        file_record = UploadedFile.objects.get(id=file_id, user=request.user)
        # Generate presigned URL (valid for 1 hour)

        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )

        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_record.s3_key
            },
            ExpiresIn=3600  # 1 hour
        )
        return redirect(download_url)
    
    except UploadedFile.DoesNotExist:
        messages.error(request, "File not found.")
        return redirect('file_list')
    except Exception as e:
        logger.error(f"Download error: {e}")
        messages.error(request, "Failed to generate download link.")
        return redirect('file_list')
    
#View classified files
@login_required

def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']

        # Generate unique filename
        file_extension = uploaded_file.name.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"uploads/{request.user.username}/{unique_filename}"

        try:
            # Read file content for classification

            file_content = uploaded_file.read()

            # Import OCRClassifier
            from .classification import OCRClassifier

            # Classify using OCR-enabled classifier

            classification, confidence, matched_patterns = OCRClassifier.classify_with_ocr(
                file_content,
                uploaded_file.name,
                uploaded_file.content_type
            )

            # Reset file pointer for S3 upload
            uploaded_file.seek(0)

            # Upload to S3

            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME

            )

            s3_client.upload_fileobj(
                uploaded_file,
                settings.AWS_STORAGE_BUCKET_NAME,
                s3_key,
                ExtraArgs={'ContentType': uploaded_file.content_type}
            )

            # Save to database with classification
            file_record = UploadedFile.objects.create(
                user=request.user,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                s3_key=s3_key,
                file_type=uploaded_file.content_type,
                classification=classification,
                classification_confidence=confidence,
                classification_patterns=json.dumps(matched_patterns[:5]),
                classified_at=timezone.now()
            )

            messages.success(request, f"File '{uploaded_file.name}' uploaded successfully!")

            return redirect('file_list')

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            messages.error(request, "Failed to upload file to cloud storage.")
            return redirect('upload_file')

        except Exception as e:
            logger.error(f"Upload error: {e}")
            messages.error(request, "An error occurred during upload.")
            return redirect('upload_file')

    return render(request, 'home/upload.html')

#my ticket
@login_required
def create_ticket(request):
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        description = request.POST.get("description", "").strip()
        department = request.POST.get("department") # <--- NEW: Citizen picks department

        if not subject or not description:
            messages.error(request, "Subject and Description are required.")
            return redirect("create_ticket")

        Ticket.objects.create(
            citizen=request.user,
            subject=subject,
            description=description,
            department=department # <--- NEW: Save Attribute
        )
        messages.success(request, "Ticket created successfully.")
        return redirect("ticket_list")

    # Pass DEPARTMENTS for dropdown
    return render(request, "tickets/create_ticket.html", {"departments": DEPARTMENTS})


@login_required
def ticket_list(request):
    user = request.user
    
    # Logic: 
    # - Citizens see ONLY their own tickets.
    # - Gov Workers see tickets based on Attribute Access (Dept + Role)
    
    is_gov = user.groups.filter(name="GovernmentWorker").exists() or user.is_staff

    if is_gov:
        # --- ABAC LOGIC ---
        try:
            # 1. Get User Attributes
            staff_profile = StaffProfile.objects.get(user=user)
            
            # 2. Filter Resources
            # Rule: Ticket Dept == User Dept  AND  Ticket Level <= User Level
            tickets = Ticket.objects.filter(
                department=staff_profile.department,
                min_clearance__lte=staff_profile.security_level
            ).order_by('-created_at')
            
            messages.info(request, f"Viewing {staff_profile.get_department_display()} Tickets.")

        except StaffProfile.DoesNotExist:
            if user.is_superuser:
                tickets = Ticket.objects.all().order_by('-created_at')
            else:
                tickets = Ticket.objects.none()
                messages.warning(request, "Account Error: No Department Attributes found.")
        # ------------------
    else:
        tickets = Ticket.objects.filter(citizen=user).order_by('-created_at')
        is_gov = False

    return render(request, "tickets/ticket_list.html", {"tickets": tickets, "is_gov": is_gov})


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user
    
    is_gov = user.groups.filter(name="GovernmentWorker").exists() or user.is_staff
    is_owner = (ticket.citizen == user)

    # Security Check: Only Owner or Gov Worker (With correct Attributes) can view
    has_access = False

    if is_owner:
        has_access = True
    elif is_gov:
        if user.is_superuser:
            has_access = True
        else:
            try:
                # ABAC Check
                staff = StaffProfile.objects.get(user=user)
                if staff.department == ticket.department and staff.security_level >= ticket.min_clearance:
                    has_access = True
            except StaffProfile.DoesNotExist:
                has_access = False

    if not has_access:
        return HttpResponseForbidden("Access Denied: Insufficient Department or Seniority clearance.")

    if request.method == "POST":
        # Only Gov Workers can reply/update status
        if is_gov:
            new_status = request.POST.get("status")
            response = request.POST.get("gov_response")
            new_sensitivity = request.POST.get("sensitivity")
            
            if new_status:
                ticket.status = new_status
            if response:
                ticket.gov_response = response
                # Auto-assign if replying and not yet assigned
                if not ticket.assigned_to:
                    ticket.assigned_to = user
            
            # Senior staff can change sensitivity
            if new_sensitivity:
                ticket.min_clearance = int(new_sensitivity)
            
            ticket.save()
            messages.success(request, "Ticket updated.")
            return redirect("ticket_detail", ticket_id=ticket.id)

    # Data to show
    context = {
        "ticket": ticket,
        "is_gov": is_gov,
        "sensitivity_levels": Ticket.TICKET_SENSITIVITY 
    }

    if is_gov:
        # Limited View for Gov Workers (Privacy)
        try:
            profile = ticket.citizen.citizenprofile
            citizen_info = {
                "username": ticket.citizen.username,
                "email": ticket.citizen.email,
                "phone": mask_phone(profile.get_phone()), # Using your helper function
                # NRIC is intentionally hidden
            }
            context["citizen_info"] = citizen_info
        except:
            context["citizen_info"] = None

    return render(request, "tickets/ticket_detail.html", context)
