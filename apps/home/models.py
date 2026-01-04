from django.db import models
from django.contrib.auth.models import User
from security.crypto import encrypt, decrypt

class CitizenProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Encrypted fields
    encrypted_nric = models.TextField()
    encrypted_address = models.TextField()
    encrypted_phone = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Hybrid Methods for Encryption/Decryption ---
    def set_nric(self, nric: str):
        self.encrypted_nric = encrypt(nric)

    def get_nric(self) -> str:
        return decrypt(self.encrypted_nric)

    def set_address(self, address: str):
        self.encrypted_address = encrypt(address)

    def get_address(self) -> str:
        return decrypt(self.encrypted_address)

    def set_phone(self, phone: str):
        self.encrypted_phone = encrypt(phone)

    def get_phone(self) -> str:
        return decrypt(self.encrypted_phone)

    # RBAC helper methods
    def is_citizen(self):
        return self.user.groups.filter(name="Citizen").exists()

    def is_gov_worker(self):
        return self.user.groups.filter(name="GovernmentWorker").exists()

    def __str__(self):
        return f"Profile of {self.user.username}"
