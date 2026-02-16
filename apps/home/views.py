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
from .models import TicketLog
from .models import CitizenProfile

from django.utils import timezone
from datetime import timedelta
from .models import TwoFactorCode, CitizenProfile
from .email_utils import send_2fa_code_email

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
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)
    
    # --- NEW FIELDS ---
    blood_type = forms.CharField(max_length=5, required=False, label="Blood Type")
    dental_stuff = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Dental records..."}), 
        required=False, 
        label="Dental Information"
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
            
            # --- NEW FIELDS ---
            blood_type = form.cleaned_data.get("blood_type")
            dental_stuff = form.cleaned_data.get("dental_stuff")

            def is_masked(value):
                return value and "*" in value

            if nric and not is_masked(nric):
                profile.set_nric(nric)
            if phone and not is_masked(phone):
                profile.set_phone(phone)
            if address:
                profile.set_address(address)
            
            # --- SAVE NEW FIELDS ---
            if blood_type:
                profile.blood_type = blood_type
            if dental_stuff:
                profile.dental_stuff = dental_stuff

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

    # --- GET REQUEST HANDLING ---
    else:
        # Pre-fill form with existing data
        initial_data = {
            "full_name": request.user.get_full_name(),
            "email": request.user.email,
            "nric": mask_nric(profile.get_nric()),
            "phone": mask_phone(profile.get_phone()),
            "address": profile.get_address(),
            # Load existing values
            "blood_type": profile.blood_type,
            "dental_stuff": profile.dental_stuff,
        }
        
        context = {
            "form_data": initial_data,
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


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").lower()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user:
            # Check if 2FA is enabled
            try:
                profile = CitizenProfile.objects.get(user=user)
                if profile.two_factor_enabled:
                    # Generate 2FA code
                    code = TwoFactorCode.generate_code()
                    expires_at = timezone.now() + timedelta(minutes=5)
                    
                    TwoFactorCode.objects.create(
                        user=user,
                        code=code,
                        expires_at=expires_at,
                        ip_address=get_client_ip(request)
                    )
                    
                    # Send email
                    email_sent = send_2fa_code_email(user, code, get_client_ip(request))
                    
                    if email_sent:
                        # Store user ID in session temporarily
                        request.session['pending_2fa_user_id'] = user.id
                        messages.success(request, f"Verification code sent to {user.email}")
                        return redirect("verify_2fa")
                    else:
                        messages.error(request, "Failed to send verification code. Please try again.")
                        return redirect("login")
                else:
                    # 2FA not enabled, log in directly
                    login(request, user)
                    return redirect("home")
                    
            except CitizenProfile.DoesNotExist:
                # No profile = no 2FA
                login(request, user)
                return redirect("home")
        else:
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

        # Generate unique filename
        file_extension = uploaded_file.name.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        s3_key = f"uploads/{request.user.username}/{unique_filename}"

        try:
            # STEP 1: Read file content for scanning and classification
            file_content = uploaded_file.read()

            # STEP 2: MALWARE SCAN (NEW)
            from .malware_scanner import MalwareScanner
            
            logger.info("=" * 50)
            logger.info("ABOUT TO CALL MALWARE SCANNER")
            logger.info(f"File size to scan: {len(file_content)} bytes")
            logger.info("=" * 50)

            is_safe, scan_result = MalwareScanner.scan_file(file_content)
            
            logger.info("=" * 50)
            logger.info(f"SCANNER RETURNED: is_safe={is_safe}, result={scan_result}")
            logger.info("=" * 50)
            
            if not is_safe:
                # Malware detected - block upload
                messages.error(request, f"🦠 Upload blocked! Malware detected: {scan_result}")
                logger.warning(f"Malware detected in upload by {request.user.username}: {scan_result}")
                return redirect('upload_file')
            
            # STEP 3: File Classification (OCR)
            from .classification import OCRClassifier

            classification, confidence, matched_patterns = OCRClassifier.classify_with_ocr(
                file_content,
                uploaded_file.name,
                uploaded_file.content_type
            )

            # Reset file pointer for S3 upload
            uploaded_file.seek(0)

            # STEP 4: Upload to S3
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

            # STEP 5: Save to database with both classification AND malware status
            file_record = UploadedFile.objects.create(
                user=request.user,
                file_name=uploaded_file.name,
                file_size=uploaded_file.size,
                s3_key=s3_key,
                file_type=uploaded_file.content_type,
                # Classification fields
                classification=classification,
                classification_confidence=confidence,
                classification_patterns=json.dumps(matched_patterns[:5]),
                classified_at=timezone.now(),
                # Malware fields
                malware_scan_status='CLEAN' if is_safe else 'INFECTED',
                malware_scan_date=timezone.now(),
                virus_name=scan_result if not is_safe else None
            )

            messages.success(
                request, 
                f"✅ File '{uploaded_file.name}' uploaded successfully!\n"
                f"Classification: {classification} (confidence: {confidence})\n"
                f"Malware Scan: {scan_result}"
            )

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


# home/views.py

@login_required
def create_ticket(request):
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        description = request.POST.get("description", "").strip()
        department = request.POST.get("department")
        category = request.POST.get("category")

        if not subject or not description:
            messages.error(request, "Subject and Description are required.")
            return redirect("create_ticket")

        Ticket.objects.create(
            citizen=request.user,
            subject=subject,
            description=description,
            department=department,
            category=category
        )
        messages.success(request, "Ticket created successfully.")
        return redirect("ticket_list")

    return render(request, "tickets/create_ticket.html", {
        "departments": DEPARTMENTS,
        "categories": Ticket.CATEGORY_CHOICES
    })

@login_required
def ticket_list(request):
    user = request.user
    is_gov = user.groups.filter(name="GovernmentWorker").exists() or user.is_staff

    if is_gov:
        try:
            staff = StaffProfile.objects.get(user=user)
            # Filter: Same Dept + Sufficient Clearance
            tickets = Ticket.objects.filter(
                department=staff.department,
                min_clearance__lte=staff.security_level
            ).order_by('-created_at')
            messages.info(request, f"Viewing {staff.get_department_display()} Tickets.")
        except StaffProfile.DoesNotExist:
            tickets = Ticket.objects.all() if user.is_superuser else Ticket.objects.none()
    else:
        # Citizen: View own tickets
        tickets = Ticket.objects.filter(citizen=user).order_by('-created_at')
        is_gov = False

    return render(request, "tickets/ticket_list.html", {"tickets": tickets, "is_gov": is_gov})

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    user = request.user
    
    # --- A. Determine Role ---
    is_gov = user.groups.filter(name="GovernmentWorker").exists() or user.is_staff
    is_owner = (ticket.citizen == user)
    
    has_access = False
    can_edit = False  # <--- Default to False (Read-Only)

    # --- B. Check Access Rights ---
    if is_owner:
        has_access = True
        can_edit = False # Citizens cannot edit gov fields
    elif is_gov:
        if user.is_superuser:
            has_access = True
            can_edit = True
        else:
            try:
                staff = StaffProfile.objects.get(user=user)
                
                # ===================================================
                # 🦷 DENTAL TICKET LOGIC
                # ===================================================
                if ticket.category == 'DENTAL':
                    # Rule 1: EthanLim has FULL access (View + Edit)
                    if user.username == "EthanLim":
                        has_access = True
                        can_edit = True
                    
                    # Rule 2: Senior Health Staff (Level 2+) can VIEW ONLY
                    # (Assuming 'HEALTH' is your department code)
                    elif staff.department == 'HEALTH' and staff.security_level >= 2:
                        has_access = True
                        can_edit = False  # <--- READ ONLY MODE
                        
                    # Rule 3: Everyone else (Juniors/Other Depts) -> BLOCKED
                    else:
                        has_access = False
                
                # ===================================================
                # 📂 STANDARD TICKET LOGIC
                # ===================================================
                else:
                    if staff.department == ticket.department and staff.security_level >= ticket.min_clearance:
                        has_access = True
                        can_edit = True
                    else:
                        has_access = False

            except StaffProfile.DoesNotExist:
                has_access = False

    # --- C. 🛑 HANDLE ACCESS DENIED ---
    if not has_access:
        TicketLog.objects.create(
            ticket=ticket,
            user=user,
            action="UNAUTHORIZED_ACCESS",
            details=f"User {user.username} blocked from viewing."
        )
        return render(request, 'home/noaccess.html', status=403)

    # --- D. ✅ HANDLE ACCESS GRANTED (Log View) ---
    if is_gov:
        TicketLog.objects.create(
            ticket=ticket,
            user=user,
            action="VIEW",
            details=f"Staff {user.username} viewed ticket."
        )

    # --- E. Handle Updates (POST Request) ---
    if request.method == "POST" and is_gov:
        # SECURITY CHECK: Ensure user has Edit rights before processing
        if not can_edit:
            messages.error(request, "⚠️ Permission Denied: You are in Read-Only mode for this ticket.")
            return redirect("ticket_detail", ticket_id=ticket.id)

        new_status = request.POST.get("status")
        response = request.POST.get("gov_response")
        new_sensitivity = request.POST.get("sensitivity")
        
        # Log the update details
        changes = []
        if new_status and new_status != ticket.status: changes.append(f"Status: {new_status}")
        if new_sensitivity: changes.append(f"Clearance: {new_sensitivity}")
        if response: changes.append("Added Response")

        TicketLog.objects.create(
            ticket=ticket,
            user=user,
            action="UPDATE",
            details=", ".join(changes)
        )

        # Apply changes
        if new_status: ticket.status = new_status
        if response:
            ticket.gov_response = response
            if not ticket.assigned_to: ticket.assigned_to = user
        if new_sensitivity: ticket.min_clearance = int(new_sensitivity)
        
        ticket.save()
        messages.success(request, "Ticket updated.")
        return redirect("ticket_detail", ticket_id=ticket.id)

    # --- F. Prepare Data for Template ---
    context = {
        "ticket": ticket,
        "is_gov": is_gov,
        "can_edit": can_edit, # <--- Pass this to template to hide/show buttons
        "sensitivity_levels": Ticket.TICKET_SENSITIVITY,
        "logs": ticket.logs.all().order_by('-timestamp')
    }

    if is_gov:
        try:
            profile = ticket.citizen.citizenprofile
            citizen_info = {
                "username": ticket.citizen.username,
                "email": ticket.citizen.email,
                "phone": mask_phone(profile.get_phone()),
                "blood_type": profile.blood_type,
            }
            
            # Privacy Filter: Only EthanLim sees raw Dental data
            if user.username == "EthanLim":
                citizen_info["dental_stuff"] = profile.dental_stuff
            elif staff.department == 'HEALTH' and staff.security_level >= 2:
                 citizen_info["dental_stuff"] = profile.dental_stuff # Senior Health can see it
            else:
                citizen_info["dental_stuff"] = "Restricted"
                
            context["citizen_info"] = citizen_info
        except:
            context["citizen_info"] = None

    return render(request, "tickets/ticket_detail.html", context)

@login_required
def view_logs(request):
    is_gov = request.user.groups.filter(name="GovernmentWorker").exists() or request.user.is_staff
    
    if not is_gov:
        # Citizens shouldn't see system logs -> Show Access Denied
        return render(request, 'home/noaccess.html', status=403)

    # Get all logs, newest first
    logs = TicketLog.objects.all().order_by('-timestamp')
    
    return render(request, "tickets/logs.html", {"logs": logs})



def verify_2fa(request):
    """Verify 2FA code"""
    
    # Check if user has pending 2FA
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        messages.error(request, "No pending verification. Please log in first.")
        return redirect("login")
    
    from django.contrib.auth.models import User
    user = User.objects.get(id=pending_user_id)
    
    if request.method == "POST":
        entered_code = request.POST.get("code", "").strip()
        
        # Find valid code
        valid_code = TwoFactorCode.objects.filter(
            user=user,
            code=entered_code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if valid_code:
            # Mark code as used
            valid_code.is_used = True
            valid_code.save()
            
            # Log user in
            login(request, user)
            
            # Clear session data
            del request.session['pending_2fa_user_id']
            
            messages.success(request, "Login successful!")
            return redirect("home")
        else:
            # Check if code exists but is expired
            expired_code = TwoFactorCode.objects.filter(
                user=user,
                code=entered_code,
                is_used=False
            ).first()
            
            if expired_code:
                messages.error(request, "Code has expired. Please request a new one.")
            else:
                messages.error(request, "Invalid verification code. Please try again.")
    
    # Calculate time remaining
    latest_code = TwoFactorCode.objects.filter(
        user=user,
        is_used=False
    ).order_by('-created_at').first()
    
    time_remaining = None
    if latest_code:
        time_remaining = int((latest_code.expires_at - timezone.now()).total_seconds())
    
    return render(request, "auth/verify_2fa.html", {
        "user_email": user.email,
        "time_remaining": time_remaining
    })


def resend_2fa_code(request):
    """Resend 2FA code"""
    
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        messages.error(request, "No pending verification.")
        return redirect("login")
    
    from django.contrib.auth.models import User
    user = User.objects.get(id=pending_user_id)
    
    # Invalidate old codes
    TwoFactorCode.objects.filter(user=user, is_used=False).update(is_used=True)
    
    # Generate new code
    code = TwoFactorCode.generate_code()
    expires_at = timezone.now() + timedelta(minutes=5)
    
    TwoFactorCode.objects.create(
        user=user,
        code=code,
        expires_at=expires_at,
        ip_address=get_client_ip(request)
    )
    
    # Send email
    email_sent = send_2fa_code_email(user, code, get_client_ip(request))
    
    if email_sent:
        messages.success(request, "New verification code sent!")
    else:
        messages.error(request, "Failed to send code. Please try again.")
    
    return redirect("verify_2fa")


@login_required
def toggle_2fa(request):
    """Enable/disable 2FA for user"""
    
    profile, created = CitizenProfile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "enable":
            if not request.user.email:
                messages.error(request, "Please add an email address to your profile before enabling 2FA.")
                return redirect("profile")
            
            profile.two_factor_enabled = True
            profile.save()
            messages.success(request, "✅ Two-Factor Authentication enabled! You'll receive a code via email on next login.")
        
        elif action == "disable":
            profile.two_factor_enabled = False
            profile.save()
            messages.success(request, "Two-Factor Authentication disabled.")
        
        return redirect("security_settings")
    
    return render(request, "auth/toggle_2fa.html", {
        "two_factor_enabled": profile.two_factor_enabled
    })


@login_required
def security_settings(request):
    """Security settings page"""
    
    profile, created = CitizenProfile.objects.get_or_create(user=request.user)
    
    # Get recent 2FA activity
    recent_codes = TwoFactorCode.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    return render(request, "auth/security_settings.html", {
        "two_factor_enabled": profile.two_factor_enabled,
        "recent_codes": recent_codes
    })