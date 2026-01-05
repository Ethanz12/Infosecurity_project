import re
from typing import Dict, List, Tuple
import PyPDF2
import io
from docx import Document
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes

class FileClassifier:
    """
    Classify files based on content patterns using regex
    """
    
    # Define classification patterns
    PATTERNS = {
        'CONFIDENTIAL': [
            r'\b(confidential|secret|private|restricted)\b',
            r'\b(ssn|social security)\s*:?\s*\d{3}-?\d{2}-?\d{4}',
            r'\b(password|passwd|pwd)\s*[:=]\s*\S+',
            r'\bAPI[_\s]?KEY\s*[:=]\s*[\w\-]+',
            r'\b(credit card|cc)\s*:?\s*\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}',
            r'\b(secret|classified|top secret)\b',
        ],
        'SENSITIVE': [
            r'\b(personal|sensitive|proprietary)\b',
            r'\b(salary|compensation|payroll|income)\b',
            r'\b(medical|health|diagnosis|patient)\b',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone numbers
            r'\b(dob|date of birth)\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'\b(nric|passport|id number)\b',
        ],
        'INTERNAL': [
            r'\b(internal use only|company confidential)\b',
            r'\b(draft|preliminary|not for distribution)\b',
            r'\b(meeting notes|minutes|memo)\b',
            r'\b(budget|forecast|projection|quarterly)\b',
        ],
        'PUBLIC': [
            r'\b(public|published|press release)\b',
            r'\b(announcement|newsletter)\b',
            r'\b(faq|frequently asked questions)\b',
            r'\b(open source|creative commons)\b',
        ],
    }
    
    # Scoring weights
    WEIGHTS = {
        'CONFIDENTIAL': 100,
        'SENSITIVE': 75,
        'INTERNAL': 50,
        'PUBLIC': 25,
    }
    
    @classmethod
    def classify_content(cls, content: str) -> Tuple[str, Dict[str, int]]:
        """
        Classify content based on regex patterns
        
        Returns:
            Tuple of (classification, scores_dict)
        """
        if not content or len(content.strip()) == 0:
            return 'UNCLASSIFIED', {}
        
        content_lower = content.lower()
        scores = {category: 0 for category in cls.PATTERNS.keys()}
        
        # Count pattern matches for each category
        for category, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                if matches:
                    # Add weight based on number of matches
                    scores[category] += len(matches) * cls.WEIGHTS[category]
        
        # Determine final classification (highest score)
        if max(scores.values()) == 0:
            return 'UNCLASSIFIED', scores
        
        classification = max(scores, key=scores.get)
        return classification, scores
    
    @classmethod
    def get_matched_patterns(cls, content: str, category: str) -> List[str]:
        """
        Get list of matched patterns for a specific category
        """
        if not content:
            return []
        
        matched = []
        content_lower = content.lower()
        
        for pattern in cls.PATTERNS.get(category, []):
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            if matches:
                matched.extend(matches[:3])  # Limit to 3 examples per pattern
        
        return matched
    
    @classmethod
    def classify_file_by_name(cls, filename: str) -> str:
        """
        Quick classification based on filename
        """
        filename_lower = filename.lower()
        
        if any(word in filename_lower for word in ['confidential', 'secret', 'private']):
            return 'CONFIDENTIAL'
        elif any(word in filename_lower for word in ['sensitive', 'personal', 'restricted']):
            return 'SENSITIVE'
        elif any(word in filename_lower for word in ['internal', 'draft', 'wip']):
            return 'INTERNAL'
        elif any(word in filename_lower for word in ['public', 'press', 'announcement']):
            return 'PUBLIC'
        
        return 'UNCLASSIFIED'


class FileReader:
    """
    Extract text content from various file types including OCR for images
    """
    
    @staticmethod
    def read_text_file(file_content: bytes) -> str:
        """Read plain text files"""
        try:
            return file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return file_content.decode('latin-1')
            except:
                return ""
    
    @staticmethod
    def read_pdf(file_content: bytes, use_ocr: bool = True) -> str:
        """Extract text from PDF (tries text extraction first, then OCR if enabled)"""
        text = ""
        
        try:
            # First try regular text extraction
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # If we got substantial text, return it
            if len(text.strip()) > 100:
                print(f"PDF text extraction successful: {len(text)} characters")
                return text
            
            # Otherwise, try OCR if enabled (PDF might be scanned images)
            if use_ocr:
                print("PDF has little text, attempting OCR...")
                try:
                    images = convert_from_bytes(file_content, dpi=300)
                    
                    for i, image in enumerate(images):
                        ocr_text = pytesseract.image_to_string(image, lang='eng')
                        if ocr_text.strip():
                            text += f"\n--- Page {i+1} (OCR) ---\n{ocr_text}\n"
                    
                    print(f"OCR completed: {len(text)} characters extracted")
                except Exception as ocr_error:
                    print(f"OCR failed for PDF: {ocr_error}")
            
            return text
            
        except Exception as e:
            print(f"PDF reading error: {e}")
            return text if text else ""
    
    @staticmethod
    def read_docx(file_content: bytes) -> str:
        """Extract text from DOCX"""
        try:
            doc_file = io.BytesIO(file_content)
            doc = Document(doc_file)
            
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            print(f"DOCX text extraction: {len(text)} characters")
            return text
        except Exception as e:
            print(f"DOCX reading error: {e}")
            return ""
    
    @staticmethod
    def read_image_ocr(file_content: bytes, filename: str = "") -> str:
        """Extract text from images using OCR"""
        try:
            image = Image.open(io.BytesIO(file_content))
            
            # Optional: Preprocess image for better OCR
            # Convert to grayscale if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Tesseract OCR
            print(f"Running OCR on image: {filename}")
            text = pytesseract.image_to_string(image, lang='eng')
            
            print(f"OCR extracted {len(text)} characters from image")
            return text
        except Exception as e:
            print(f"OCR error on {filename}: {e}")
            return ""
    
    @classmethod
    def extract_text(cls, file_content: bytes, file_type: str, filename: str) -> str:
        """
        Extract text based on file type (with OCR support)
        """
        file_extension = filename.lower().split('.')[-1]
        
        print(f"Extracting text from: {filename} (type: {file_type}, ext: {file_extension})")
        
        # Text files
        if file_extension in ['txt', 'csv', 'log', 'md', 'json', 'xml']:
            return cls.read_text_file(file_content)
        
        # PDF files (with OCR fallback)
        elif file_extension == 'pdf' or 'pdf' in file_type.lower():
            return cls.read_pdf(file_content, use_ocr=True)
        
        # Word documents
        elif file_extension in ['docx', 'doc'] or 'word' in file_type.lower():
            return cls.read_docx(file_content)
        
        # Image files (OCR)
        elif file_extension in ['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'gif'] or 'image' in file_type.lower():
            return cls.read_image_ocr(file_content, filename)
        
        else:
            # Try reading as text as last resort
            print(f"Unknown file type, attempting text read: {filename}")
            return cls.read_text_file(file_content)


class OCRClassifier:
    """
    Specialized classifier for image-heavy documents with OCR support
    """
    
    @classmethod
    def classify_with_ocr(cls, file_content: bytes, filename: str, file_type: str) -> Tuple[str, int, List[str]]:
        """
        Full classification pipeline with OCR support
        
        Returns:
            Tuple of (classification, confidence, matched_patterns)
        """
        print(f"\n=== Starting classification for: {filename} ===")
        
        # Extract text (with OCR if needed)
        extracted_text = FileReader.extract_text(file_content, file_type, filename)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            print(f"No text extracted (length: {len(extracted_text)}), classifying by filename only")
            # No text extracted, classify by filename only
            classification = FileClassifier.classify_file_by_name(filename)
            return classification, 0, []
        
        print(f"Text extracted successfully: {len(extracted_text)} characters")
        
        # Classify based on content
        classification, scores = FileClassifier.classify_content(extracted_text)
        confidence = scores.get(classification, 0)
        
        print(f"Classification scores: {scores}")
        print(f"Selected classification: {classification} (confidence: {confidence})")
        
        # Get matched patterns
        matched_patterns = FileClassifier.get_matched_patterns(extracted_text, classification)
        
        # If still unclassified, try filename
        if classification == 'UNCLASSIFIED':
            print("Content-based classification returned UNCLASSIFIED, trying filename")
            classification = FileClassifier.classify_file_by_name(filename)
        
        print(f"=== Final: {classification} with confidence {confidence} ===\n")
        
        return classification, confidence, matched_patterns