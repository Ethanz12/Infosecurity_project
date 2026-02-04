from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from security.crypto import encrypt, decrypt 

# --- CONFIGURATION: Singapore Departments (ABAC Attributes) ---
DEPARTMENTS = [
    ('HEALTH', 'Health (MOH)'),
    ('FINANCE', 'Finance (MOF/IRAS)'),
    ('GENERAL', 'General / Municipal (Town Council)'),
]

# --- CONFIGURATION: Access Levels (New Attribute) ---
ACCESS_LEVELS = [
    (1, 'Junior Officer'),
    (2, 'Senior Manager'),
]

# ----------------------------
# Citizen Profile (Unchanged)
# ----------------------------

class CitizenProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Encrypted fields (Stored as ciphertext)
    encrypted_nric = models.TextField(blank=True, null=True)
    encrypted_address = models.TextField(blank=True, null=True)
    encrypted_phone = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Encryption Helper Methods --- 
    def set_nric(self, nric: str): 
        if nric: self.encrypted_nric = encrypt(nric)  

    def get_nric(self) -> str:
        return decrypt(self.encrypted_nric) if self.encrypted_nric else ""

    def set_address(self, address: str):
        if address: self.encrypted_address = encrypt(address)

    def get_address(self) -> str:
        return decrypt(self.encrypted_address) if self.encrypted_address else ""

    def set_phone(self, phone: str):
        if phone: self.encrypted_phone = encrypt(phone)

    def get_phone(self) -> str:
        return decrypt(self.encrypted_phone) if self.encrypted_phone else ""

    def __str__(self):
        return f"Profile of {self.user.username}"

# --- SIGNALS (Automation) ---
@receiver(post_save, sender=User)
def create_citizen_profile(sender, instance, created, **kwargs):
    """Automatically create a profile when a User is created."""
    if created:
        CitizenProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_citizen_profile(sender, instance, **kwargs):
    """Ensure profile saves when user saves."""
    if hasattr(instance, 'citizenprofile'):
        instance.citizenprofile.save()


# ----------------------------
# UploadedFile (Unchanged - Teammate's Work)
# ----------------------------

class UploadedFile(models.Model):
    CLASSIFICATION_CHOICES = [
        ('UNCLASSIFIED', 'Unclassified'),
        ('PUBLIC', 'Public'),
        ('INTERNAL', 'Internal Use Only'),
        ('SENSITIVE', 'Sensitive'),
        ('CONFIDENTIAL', 'Confidential'),
    ]
        
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()  # in bytes
    s3_key = models.CharField(max_length=500)  # S3 path
    upload_date = models.DateTimeField(auto_now_add=True)
    file_type = models.CharField(max_length=100)
    
    # Classification fields
    classification = models.CharField(
        max_length=50, 
        choices=CLASSIFICATION_CHOICES,
        default='UNCLASSIFIED'
    )

    classification_confidence = models.IntegerField(default=0)  # Score
    classification_patterns = models.TextField(blank=True, null=True)  # Matched patterns as JSON
    classified_at = models.DateTimeField(blank=True, null=True)  # When it was classified

    def __str__(self):
            return f"{self.file_name} - {self.user.username} [{self.classification}]"
    
    class Meta:
            ordering = ['-upload_date']

    def get_classification_badge_color(self):
        """Return color for classification badge"""
        colors = {
            'CONFIDENTIAL': '#dc3545',  # Red
            'SENSITIVE': '#fd7e14',     # Orange
            'INTERNAL': '#ffc107',      # Yellow
            'PUBLIC': '#28a745',        # Green
            'UNCLASSIFIED': '#6c757d',  # Gray
        }
        return colors.get(self.classification, '#6c757d')


# ----------------------------
# Ticket System (Updated for ABAC - Departments + Levels)
# ----------------------------

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    TICKET_SENSITIVITY = [
        (1, 'Normal - Viewable by all staff'),
        (2, 'Sensitive - Senior Staff Only'),
    ]

    # Link to the Citizen who created it
    citizen = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    
    # Ticket Details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')

    # --- ATTRIBUTE 1: Department Routing ---
    department = models.CharField(
        max_length=50, 
        choices=DEPARTMENTS, 
        default='GENERAL',
        help_text="The government department this ticket belongs to."
    )

    # --- ATTRIBUTE 2: Sensitivity Level ---
    # Citizens don't set this; it defaults to 1. 
    # Logic: Gov Staff can escalate a ticket to Level 2 (Sensitive), hiding it from Juniors.
    min_clearance = models.IntegerField(
        choices=TICKET_SENSITIVITY, 
        default=1,
        help_text="Minimum clearance level required to view this ticket."
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Government Worker Response (Optional)
    gov_response = models.TextField(blank=True, null=True)
    
    # Optional: Link to a specific Gov Worker if they "claim" the ticket
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="assigned_tickets"
    )

    def __str__(self):
        return f"[{self.get_department_display()}] {self.subject} (Lvl {self.min_clearance})"


# ----------------------------
# Staff Profile (Updated for ABAC - Departments + Levels)
# ----------------------------

class StaffProfile(models.Model):
    """
    Stores the 'Attributes' for government workers.
    This avoids creating roles like 'Senior Health Officer'.
    Instead, we check: if user.dept == ticket.dept AND user.level >= ticket.min_clearance
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Attribute 1: Department
    department = models.CharField(max_length=50, choices=DEPARTMENTS)
    
    # Attribute 2: Seniority / Clearance Level
    security_level = models.IntegerField(
        choices=ACCESS_LEVELS, 
        default=1,
        help_text="1 = Junior (Normal Access), 2 = Senior (Can see sensitive tickets)"
    )

    def __str__(self):
        return f"{self.user.username} | {self.get_department_display()} | Lvl {self.security_level}"