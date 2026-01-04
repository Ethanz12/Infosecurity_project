# security/crypto.py
from cryptography.fernet import Fernet
import os

# Load encryption key from environment variable
# You can generate one with: Fernet.generate_key().decode()
KEY = os.getenv("FIELD_ENCRYPTION_KEY")

if not KEY:
    raise ValueError("FIELD_ENCRYPTION_KEY environment variable not set!")

fernet = Fernet(KEY.encode())

# Encrypt a string
def encrypt(value: str) -> str:
    if not value:
        return ""
    return fernet.encrypt(value.encode()).decode()

# Decrypt a string
def decrypt(value: str) -> str:
    if not value:
        return ""
    return fernet.decrypt(value.encode()).decode()
