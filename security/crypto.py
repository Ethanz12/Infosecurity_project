# security/crypto.py
from cryptography.fernet import Fernet
import os
import logging

logger = logging.getLogger(__name__)

# 1. Load the key from the environment variable
# IMPORTANT: This name must match your .env file exactly!
key_str = os.getenv("FIELD_ENCRYPTION_KEY") #I implemented secure key management. The encryption key is loaded from an Environment Variable, not hardcoded in the script. This prevents the key from being leaked if the source code is stolen."

# 2. Safety Check: If key is missing, generate a temporary one but WARN the user.
if not key_str:
    logger.warning("⚠️ CRITICAL SECURITY WARNING: FIELD_ENCRYPTION_KEY not found in environment!")
    logger.warning("Using a temporary random key. DATA WILL BE LOST upon restart.")
    key_str = Fernet.generate_key().decode()

# 3. Initialize the Cipher
cipher = Fernet(key_str.encode())

def encrypt(txt: str) -> str:
    if not txt: return ""
    return cipher.encrypt(txt.encode()).decode()

def decrypt(txt: str) -> str:
    if not txt: return ""
    try:
        return cipher.decrypt(txt.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return "[Decryption Error]"