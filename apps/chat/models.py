# chat/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from security.crypto import encrypt, decrypt  # Your existing encryption functions
import json


# ----------------------------
# Conversation Model
# ----------------------------
class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        participant_names = ", ".join([user.username for user in self.participants.all()])
        return f"Conversation ({self.id}) between {participant_names}"


# ----------------------------
# Message Model
# ----------------------------
class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")

    # Original content (encrypted)
    encrypted_content = models.TextField()

    # Redacted content for display
    redacted_content = models.TextField(blank=True, null=True)

    # Track whether recipient has read
    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    # ----------------------------
    # Helper Methods
    # ----------------------------
    def set_content(self, plain_text: str):
        """Encrypt and save the message."""
        if plain_text:
            self.encrypted_content = encrypt(plain_text)

    def get_content(self) -> str:
        """Decrypt message for internal use."""
        if self.encrypted_content:
            return decrypt(self.encrypted_content)
        return ""

    def set_redacted_content(self, redacted_text: str):
        """Store redacted version for display in inbox/room."""
        self.redacted_content = redacted_text
        # Cache it for quick access
        self._redacted_cache = redacted_text

    def get_redacted_content(self) -> str:
        """
        Return the redacted version for display.
        Guarantees a string, never a list or None.
        """
        if hasattr(self, '_redacted_cache'):
            return self._redacted_cache
        if isinstance(self.redacted_content, (list, tuple)):
            return str(self.redacted_content[0]) if self.redacted_content else "[REDACTED]"
        if self.redacted_content:
            return self.redacted_content
        return "[REDACTED]"

    def __str__(self):
        return f"Message {self.id} in Conversation {self.conversation.id} by {self.sender.username}"


# ----------------------------
# Admin-configurable sensitive patterns
# ----------------------------
class SensitivePattern(models.Model):
    """
    Admins can define patterns to automatically redact.
    Example types: PII, phone, NRIC, email, custom regex
    """
    name = models.CharField(max_length=50)
    regex = models.TextField(help_text="Python regex pattern to match sensitive data")
    active = models.BooleanField(default=True)

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.name} ({status})"