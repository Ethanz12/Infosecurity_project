# chat/redaction.py
import re
from .models import SensitivePattern

# -----------------------------
# Default patterns fallback
# -----------------------------
# DEFAULT_PATTERNS = {
#     # NRIC: allow optional spaces between letters and digits
#     "nric": r"(?i)\b[STFGM]\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*[A-Z]\b",
#     # Email: allow optional spaces around @ and dot
#     "email": r"(?i)\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b",
#     # Phone: digits with optional spaces
#     "phone": r"\b\d[\d\s]{7,14}\d\b"
# }
DEFAULT_PATTERNS = {
    # NRIC / FIN (Singapore-specific ID numbers)
    "nric": r"(?i)\b[STFGM]\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*[A-Z]\b",

    # Email addresses
    "email": r"(?i)\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b",

    # Phone numbers (local & international)
    "phone": r"\b(?:\+65\s*)?\d[\d\s]{7,14}\d\b",

    # Postal codes (Singapore-style: 6 digits)
    "postal": r"\b\d{6}\b",

    # Bank account numbers (generic, 6–20 digits)
    "bank_account": r"\b\d{6,20}\b",

    # Passport numbers (Singapore & general: 6–9 alphanumeric)
    "passport": r"\b[A-Z0-9]{6,9}\b",

    # Credit/Debit cards (Visa, MasterCard, Amex, etc.)
    "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",

    # Date of Birth (YYYY-MM-DD or DD/MM/YYYY)
    "dob_iso": r"\b\d{4}-\d{2}-\d{2}\b",
    "dob_slash": r"\b\d{2}/\d{2}/\d{4}\b",

    # Addresses (basic patterns for street + number)
    "address": r"\b\d{1,5}\s+[A-Za-z0-9\s]+(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b",

    # Vehicle registration numbers (Singapore: e.g., SGB1234A)
    "vehicle_reg": r"\b[S][A-Z]\s*\d{1,4}[A-Z]?\b",

    # Government email / domain identifiers (to catch internal references)
    "gov_email": r"(?i)\b[A-Za-z0-9._%+-]+\s*@\s*(?:gov\.sg|moe\.gov\.sg|mha\.gov\.sg)\b",

    # IP addresses (IPv4)
    "ip_address": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",

    # URLs
    "url": r"(https?://[^\s]+)",

    # Any generic confidential keywords (optional, for policy-related redaction)
    "confidential": r"(?i)\b(secret|classified|confidential|internal use only|restricted)\b",
}
# -----------------------------
# Optional spaCy NLP model
# -----------------------------
try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
    print("✅ spaCy NLP loaded for advanced redaction")
except (ImportError, OSError):
    NLP = None
    print("⚠️ spaCy NLP not available — falling back to regex-only redaction")


# -----------------------------
# Main redaction function
# -----------------------------
def redact_text(text: str, custom_patterns: dict = None):
    """
    Returns a tuple: (redacted_text, redaction_metadata)
    Redacts using:
      1. Database patterns (SensitivePattern model)
      2. Default patterns
      3. Optional custom patterns
      4. Optional NLP detection
    """
    # 1️⃣ Load active DB patterns
    from django.apps import apps
    db_patterns = {}
    try:
        SensitivePatternModel = apps.get_model("chat", "SensitivePattern")
        for sp in SensitivePatternModel.objects.filter(active=True):
            db_patterns[sp.name.lower()] = sp.regex
    except Exception:
        db_patterns = {}

    # 2️⃣ Merge patterns
    patterns = DEFAULT_PATTERNS.copy()
    patterns.update(db_patterns)
    if custom_patterns:
        patterns.update(custom_patterns)

    redacted_text = text
    redaction_metadata = {}

    # 3️⃣ Normalize spaces for NRIC & emails for consistent matching
    normalized_text = redacted_text
    normalized_text = re.sub(
        r'([STFGM])\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*([A-Z])',
        lambda m: ''.join(m.groups()),
        normalized_text,
        flags=re.IGNORECASE
    )
    normalized_text = re.sub(
        r'([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})',
        lambda m: f"{m.group(1)}@{m.group(2)}.{m.group(3)}",
        normalized_text
    )

    # 4️⃣ Apply regex redaction
    for key, pattern in patterns.items():
        try:
            matches = re.findall(pattern, normalized_text)
            if matches:
                # Ensure matches are strings
                matches_str = [m if isinstance(m, str) else str(m) for m in matches]
                redaction_metadata[key] = matches_str
                # Safe replace in original text (redacted_text)
                redacted_text = re.sub(pattern, f"[{key.upper()} REDACTED]", redacted_text)
        except re.error:
            continue  # skip invalid regex

    # 5️⃣ Optional NLP-based redaction
    if NLP:
        doc = NLP(redacted_text)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE", "LOC", "FAC"]:
                ent_text = ent.text
                placeholder = f"[{ent.label_} REDACTED]"
                # Store in metadata safely
                redaction_metadata.setdefault(ent.label_.lower(), []).append(ent_text)
                # Replace all occurrences safely (case-insensitive)
                redacted_text = re.sub(re.escape(ent_text), placeholder, redacted_text, flags=re.IGNORECASE)

    return redacted_text, redaction_metadata