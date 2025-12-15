from django.db import models
from django.contrib.auth.models import User

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
    
    # Classification fields (UPDATED)
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