# models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from security.crypto import encrypt, decrypt 

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