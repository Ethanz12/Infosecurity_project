from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import logging
from django.db import connection, DatabaseError

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
            
            # Save to database
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
            messages.error(request, "An error occurred during upload.")
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
            
            # Extract text from file
            extracted_text = FileReader.extract_text(
                file_content, 
                uploaded_file.content_type,
                uploaded_file.name
            )
            
            # Classify the content
            classification, scores = FileClassifier.classify_content(extracted_text)
            
            # Get matched patterns for transparency
            matched_patterns = FileClassifier.get_matched_patterns(extracted_text, classification)
            
            # If no content-based classification, try filename
            if classification == 'UNCLASSIFIED':
                classification = FileClassifier.classify_file_by_name(uploaded_file.name)
            
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
                classification_confidence=scores.get(classification, 0),
                classification_patterns=json.dumps(matched_patterns[:5]),  # Store top 5
                classified_at=timezone.now()
            )
            
            messages.success(
                request, 
                f"File '{uploaded_file.name}' uploaded and classified as: {classification}"
            )
            return redirect('file_list')
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            messages.error(request, "Failed to upload file to cloud storage.")
            return redirect('upload_file')
        except Exception as e:
            logger.error(f"Upload error: {e}")
            messages.error(request, f"An error occurred during upload: {str(e)}")
            return redirect('upload_file')
    
    return render(request, 'home/upload.html')