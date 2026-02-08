# # # # chat/redaction.py
# # # import re
# # # from .models import SensitivePattern
# # #
# # # # Default patterns fallback
# # # DEFAULT_PATTERNS = {
# # #     "nric": r"(?i)\b[STFGM]\d{7}[A-Z]\b",  # Singapore NRIC, case-insensitive
# # #     "email": r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",  # email, ignore case
# # #     "phone": r"\b\d{8,15}\b"  # phone numbers (digits only, no letters)
# # # }
# # #
# # #
# # # def redact_text(text: str, custom_patterns: dict = None):
# # #     """
# # #     Returns a tuple: (redacted_text, redaction_metadata)
# # #     Redacts using:
# # #       1. Database patterns (SensitivePattern model)
# # #       2. Default patterns
# # #       3. Optional custom patterns
# # #     """
# # #     # 1️⃣ Load active DB patterns
# # #     db_patterns = {}
# # #     from django.apps import apps
# # #     try:
# # #         SensitivePattern = apps.get_model("chat", "SensitivePattern")
# # #         for sp in SensitivePattern.objects.filter(active=True):
# # #             db_patterns[sp.name.lower()] = sp.regex
# # #     except Exception:
# # #         db_patterns = {}
# # #
# # #     # 2️⃣ Merge all patterns
# # #     patterns = DEFAULT_PATTERNS.copy()
# # #     patterns.update(db_patterns)
# # #     if custom_patterns:
# # #         patterns.update(custom_patterns)
# # #
# # #     redacted_text = text
# # #     redaction_metadata = {}
# # #
# # #     # 3️⃣ Apply regex redaction
# # #     for key, pattern in patterns.items():
# # #         try:
# # #             matches = re.findall(pattern, redacted_text)
# # #             if matches:
# # #                 redaction_metadata[key] = matches
# # #                 # Replace all matches safely
# # #                 redacted_text = re.sub(pattern, f"[{key.upper()} REDACTED]", redacted_text)
# # #         except re.error:
# # #             continue  # skip invalid regex
# # #
# # #     return redacted_text, redaction_metadata
# #
# # # chat/redaction.py
# # import re
# # from .models import SensitivePattern
# #
# # # Optional: NLP-based redaction
# # try:
# #     import spacy
# #     NLP = spacy.load("en_core_web_sm")  # Pretrained English model
# # except ImportError:
# #     NLP = None  # NLP redaction will be skipped if spaCy not installed
# #
# # # Default patterns fallback (regex)
# # DEFAULT_PATTERNS = {
# #     "nric": r"(?i)\b[STFGM]\d{7}[A-Z]\b",  # Singapore NRIC, case-insensitive
# #     "email": r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",  # email, ignore case
# #     "phone": r"\b\d{8,15}\b"  # phone numbers (digits only, no letters)
# # }
# #
# #
# # def redact_text(text: str, custom_patterns: dict = None):
# #     """
# #     Returns a tuple: (redacted_text, redaction_metadata)
# #     Redacts using:
# #       1. Database patterns (SensitivePattern model)
# #       2. Default patterns
# #       3. Optional custom patterns
# #       4. NLP-based entity detection (PERSON, ORG, GPE, LOC, etc.)
# #     """
# #     # 1️⃣ Load active DB patterns
# #     db_patterns = {}
# #     from django.apps import apps
# #     try:
# #         SensitivePatternModel = apps.get_model("chat", "SensitivePattern")
# #         for sp in SensitivePatternModel.objects.filter(active=True):
# #             db_patterns[sp.name.lower()] = sp.regex
# #     except Exception:
# #         db_patterns = {}
# #
# #     # 2️⃣ Merge all patterns
# #     patterns = DEFAULT_PATTERNS.copy()
# #     patterns.update(db_patterns)
# #     if custom_patterns:
# #         patterns.update(custom_patterns)
# #
# #     redacted_text = text
# #     redaction_metadata = {}
# #
# #     # 3️⃣ Apply regex redaction
# #     for key, pattern in patterns.items():
# #         try:
# #             matches = re.findall(pattern, redacted_text)
# #             if matches:
# #                 redaction_metadata[key] = matches
# #                 redacted_text = re.sub(pattern, f"[{key.upper()} REDACTED]", redacted_text)
# #         except re.error:
# #             continue  # skip invalid regex
# #
# #     # 4️⃣ NLP-based redaction
# #     if NLP:
# #         doc = NLP(redacted_text)
# #         for ent in doc.ents:
# #             if ent.label_ in ["PERSON", "ORG", "GPE", "LOC", "FAC"]:
# #                 ent_text = ent.text
# #                 placeholder = f"[{ent.label_} REDACTED]"
# #                 if ent_text not in redaction_metadata:
# #                     redaction_metadata.setdefault(ent.label_.lower(), []).append(ent_text)
# #                 # Replace all occurrences safely (case-insensitive)
# #                 redacted_text = re.sub(re.escape(ent_text), placeholder, redacted_text, flags=re.IGNORECASE)
# #
# #     return redacted_text, redaction_metadata
#
#
# # chat/redaction.py
# import re
# from .models import SensitivePattern
#
# # Default patterns fallback
# DEFAULT_PATTERNS = {
#     "nric": r"(?i)\b[STFGM]\d{7}[A-Z]\b",  # Singapore NRIC, case-insensitive
#     "email": r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
#     "phone": r"\b\d{8,15}\b"
# }
#
# # Attempt to load spaCy NLP model
# try:
#     import spacy
#     NLP = spacy.load("en_core_web_sm")
#     print("✅ spaCy NLP loaded for advanced redaction")
# except (ImportError, OSError):
#     NLP = None
#     print("⚠️ spaCy NLP not available — falling back to regex-only redaction")
#
#
# def redact_text(text: str, custom_patterns: dict = None):
#     """
#     Returns (redacted_text, redaction_metadata)
#     """
#     # 1️⃣ Load active DB patterns
#     from django.apps import apps
#     db_patterns = {}
#     try:
#         SensitivePattern = apps.get_model("chat", "SensitivePattern")
#         for sp in SensitivePattern.objects.filter(active=True):
#             db_patterns[sp.name.lower()] = sp.regex
#     except Exception:
#         db_patterns = {}
#
#     # 2️⃣ Merge all patterns
#     patterns = DEFAULT_PATTERNS.copy()
#     patterns.update(db_patterns)
#     if custom_patterns:
#         patterns.update(custom_patterns)
#
#     redacted_text = text
#     redaction_metadata = {}
#
#     # 3️⃣ Apply regex redaction
#     for key, pattern in patterns.items():
#         try:
#             matches = re.findall(pattern, redacted_text)
#             if matches:
#                 redaction_metadata[key] = matches
#                 redacted_text = re.sub(pattern, f"[{key.upper()} REDACTED]", redacted_text)
#         except re.error:
#             continue
#
#     # 4️⃣ Optional NLP-based detection
#     if NLP:
#         doc = NLP(redacted_text)
#         # Example: redact PERSON entities
#         for ent in doc.ents:
#             if ent.label_ in ["PERSON", "ORG", "GPE"]:
#                 redacted_text = redacted_text.replace(ent.text, f"[{ent.label_} REDACTED]")
#                 redaction_metadata[ent.label_] = redaction_metadata.get(ent.label_, []) + [ent.text]
#
#     return redacted_text, redaction_metadata

# chat/redaction.py
import re
from .models import SensitivePattern

# Default patterns fallback
DEFAULT_PATTERNS = {
    # NRIC: allow optional spaces between digits and final letter
    "nric": r"(?i)\b[STFGM]\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*\d\s*[A-Z]\b",
    # Email: allow optional spaces around @ and dot
    "email": r"(?i)\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b",
    # Phone: still digits only, can add spaces optionally
    "phone": r"\b\d[\d\s]{7,14}\d\b"
}

# Attempt to load spaCy NLP model
try:
    import spacy
    NLP = spacy.load("en_core_web_sm")
    print("✅ spaCy NLP loaded for advanced redaction")
except (ImportError, OSError):
    NLP = None
    print("⚠️ spaCy NLP not available — falling back to regex-only redaction")


def redact_text(text: str, custom_patterns: dict = None):
    """
    Returns (redacted_text, redaction_metadata)
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
        SensitivePattern = apps.get_model("chat", "SensitivePattern")
        for sp in SensitivePattern.objects.filter(active=True):
            db_patterns[sp.name.lower()] = sp.regex
    except Exception:
        db_patterns = {}

    # 2️⃣ Merge all patterns
    patterns = DEFAULT_PATTERNS.copy()
    patterns.update(db_patterns)
    if custom_patterns:
        patterns.update(custom_patterns)

    redacted_text = text
    redaction_metadata = {}

    # 3️⃣ Normalize spaces for NRIC & emails before redacting
    # Remove internal spaces for matching
    normalized_text = redacted_text
    normalized_text = re.sub(r'([STFGM])\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*(\d)\s*([A-Z])',
                             lambda m: ''.join(m.groups()), normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})',
                             lambda m: f"{m.group(1)}@{m.group(2)}.{m.group(3)}", normalized_text)

    # 4️⃣ Apply regex redaction
    for key, pattern in patterns.items():
        try:
            matches = re.findall(pattern, normalized_text)
            if matches:
                redaction_metadata[key] = matches
                redacted_text = re.sub(pattern, f"[{key.upper()} REDACTED]", redacted_text)
        except re.error:
            continue

    # 5️⃣ Optional NLP-based detection
    if NLP:
        doc = NLP(redacted_text)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "GPE"]:
                redacted_text = redacted_text.replace(ent.text, f"[{ent.label_} REDACTED]")
                redaction_metadata[ent.label_] = redaction_metadata.get(ent.label_, []) + [ent.text]

    return redacted_text, redaction_metadata
