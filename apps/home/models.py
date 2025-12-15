from django.db import models

# Create your models here.

from django.contrib.auth.models import User

class UploadedFile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()  # in bytes
    s3_key = models.CharField(max_length=500)  # S3 path
    upload_date = models.DateTimeField(auto_now_add=True)
    file_type = models.CharField(max_length=100)
    classification = models.CharField(max_length=50, null=True, blank=True)  # For future AI classification
    
    def __str__(self):
        return f"{self.file_name} - {self.user.username}"
    
    class Meta:
        ordering = ['-upload_date']