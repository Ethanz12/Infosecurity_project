import re
from typing import Dict, List, Tuple

#File Reading Utility
import PyPDF2
import io
from docx import Document
class FileClassifier:
    """
    Classify files based on content patterns using regex
    """
    
    # Define classification patterns
    PATTERNS = {
        'CONFIDENTIAL': [
            r'\b(confidential|secret|private|restricted)\b',
            r'\b(ssn|social security)\s*:?\s*\d{3}-\d{2}-\d{4}',
            r'\b(password|passwd|pwd)\s*[:=]\s*\S+',
            r'\bAPI[_\s]?KEY\s*[:=]\s*[\w\-]+',
            r'\b(credit card|cc)\s*:?\s*\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}',
        ],
        'SENSITIVE': [
            r'\b(personal|sensitive|proprietary)\b',
            r'\b(salary|compensation|payroll)\b',
            r'\b(medical|health|diagnosis)\b',
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone numbers
            r'\b(dob|date of birth)\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        ],
        'INTERNAL': [
            r'\b(internal use only|company confidential)\b',
            r'\b(draft|preliminary|not for distribution)\b',
            r'\b(meeting notes|minutes)\b',
            r'\b(budget|forecast|projection)\b',
        ],
        'PUBLIC': [
            r'\b(public|published|press release)\b',
            r'\b(announcement|newsletter)\b',
            r'\b(faq|frequently asked questions)\b',
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
    

#File Reading
class FileReader:
    """
    Extract text content from various file types
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
    def read_pdf(file_content: bytes) -> str:
        """Extract text from PDF"""
        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text
        except Exception as e:
            print(f"PDF reading error: {e}")
            return ""
    
    @staticmethod
    def read_docx(file_content: bytes) -> str:
        """Extract text from DOCX"""
        try:
            doc_file = io.BytesIO(file_content)
            doc = Document(doc_file)
            
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return text
        except Exception as e:
            print(f"DOCX reading error: {e}")
            return ""
    
    @classmethod
    def extract_text(cls, file_content: bytes, file_type: str, filename: str) -> str:
        """
        Extract text based on file type
        """
        file_extension = filename.lower().split('.')[-1]
        
        if file_extension in ['txt', 'csv', 'log', 'md']:
            return cls.read_text_file(file_content)
        elif file_extension == 'pdf' or 'pdf' in file_type:
            return cls.read_pdf(file_content)
        elif file_extension in ['docx', 'doc'] or 'word' in file_type:
            return cls.read_docx(file_content)
        else:
            # Try reading as text
            return cls.read_text_file(file_content)