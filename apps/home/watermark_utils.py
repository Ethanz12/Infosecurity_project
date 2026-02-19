# apps/home/watermark_utils.py

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PyPDF2 import PdfReader, PdfWriter
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import os
import logging
from PIL import Image, ImageDraw, ImageFont
import tempfile

logger = logging.getLogger(__name__)


class DocumentWatermarker:
    """Add classification watermarks to PDF and Word documents"""
    
    # Watermark styling based on classification
    WATERMARK_CONFIG = {
        'CONFIDENTIAL': {
            'text': 'CONFIDENTIAL',
            'color': (220, 53, 69),  # Red
            'opacity': 0.3
        },
        'SENSITIVE': {
            'text': 'SENSITIVE',
            'color': (253, 126, 20),  # Orange
            'opacity': 0.3
        },
        'INTERNAL': {
            'text': 'INTERNAL USE ONLY',
            'color': (255, 193, 7),  # Yellow/Gold
            'opacity': 0.3
        }
    }
    
    @classmethod
    def should_watermark(cls, classification):
        """Check if this classification level requires watermarking"""
        return classification in cls.WATERMARK_CONFIG
    
    @classmethod
    def add_watermark_to_pdf(cls, input_pdf_bytes, classification):
        """
        Add diagonal watermark to every page of a PDF
        
        Args:
            input_pdf_bytes: bytes of the original PDF
            classification: str classification level
            
        Returns:
            bytes: watermarked PDF
        """
        if not cls.should_watermark(classification):
            return input_pdf_bytes
        
        try:
            config = cls.WATERMARK_CONFIG[classification]
            
            # Read input PDF
            input_pdf = io.BytesIO(input_pdf_bytes)
            reader = PdfReader(input_pdf)
            writer = PdfWriter()
            
            # Create watermark PDF for one page
            watermark_buffer = io.BytesIO()
            c = canvas.Canvas(watermark_buffer, pagesize=letter)
            
            # Get page dimensions
            page_width = letter[0]
            page_height = letter[1]
            
            # Configure watermark appearance
            c.setFillColorRGB(
                config['color'][0] / 255,
                config['color'][1] / 255,
                config['color'][2] / 255,
                alpha=config['opacity']
            )
            c.setFont("Helvetica-Bold", 60)
            
            # Save state and rotate for diagonal text
            c.saveState()
            c.translate(page_width / 2, page_height / 2)
            c.rotate(45)
            
            # Draw watermark text (centered)
            text_width = c.stringWidth(config['text'], "Helvetica-Bold", 60)
            c.drawString(-text_width / 2, 0, config['text'])
            
            c.restoreState()
            c.save()
            
            # Create watermark PDF object
            watermark_buffer.seek(0)
            watermark_pdf = PdfReader(watermark_buffer)
            watermark_page = watermark_pdf.pages[0]
            
            # Apply watermark to each page
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page.merge_page(watermark_page)
                writer.add_page(page)
            
            # Write output
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)
            
            logger.info(f"Added {classification} watermark to PDF ({len(reader.pages)} pages)")
            return output_buffer.read()
            
        except Exception as e:
            logger.error(f"Failed to watermark PDF: {e}")
            # Return original if watermarking fails
            return input_pdf_bytes
    
    @classmethod
    def add_watermark_to_docx(cls, input_docx_bytes, classification):
        """
        Add watermark to header of Word document
        
        Args:
            input_docx_bytes: bytes of the original Word doc
            classification: str classification level
            
        Returns:
            bytes: watermarked Word document
        """
        if not cls.should_watermark(classification):
            return input_docx_bytes
        
        try:
            config = cls.WATERMARK_CONFIG[classification]
            
            # Load document
            doc_buffer = io.BytesIO(input_docx_bytes)
            doc = Document(doc_buffer)
            
            # Add watermark to header of first section
            section = doc.sections[0]
            header = section.header
            
            # Create watermark paragraph in header
            watermark = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
            watermark.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # Add watermark text
            run = watermark.add_run(config['text'])
            run.font.size = Pt(48)
            run.font.bold = True
            run.font.color.rgb = RGBColor(
                config['color'][0],
                config['color'][1],
                config['color'][2]
            )
            
            # Add watermark to footer as well for visibility
            footer = section.footer
            footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
            footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            footer_run = footer_para.add_run(f"[ {config['text']} ]")
            footer_run.font.size = Pt(10)
            footer_run.font.bold = True
            footer_run.font.color.rgb = RGBColor(
                config['color'][0],
                config['color'][1],
                config['color'][2]
            )
            
            # Save to bytes
            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            output_buffer.seek(0)
            
            logger.info(f"Added {classification} watermark to Word document")
            return output_buffer.read()
            
        except Exception as e:
            logger.error(f"Failed to watermark Word document: {e}")
            return input_docx_bytes
    
    @classmethod
    def add_watermark_to_image(cls, input_image_bytes, classification, image_format='PNG'):
        """
        Add watermark to image files
        
        Args:
            input_image_bytes: bytes of the original image
            classification: str classification level
            image_format: str format (PNG, JPEG, etc.)
            
        Returns:
            bytes: watermarked image
        """
        if not cls.should_watermark(classification):
            return input_image_bytes
        
        try:
            config = cls.WATERMARK_CONFIG[classification]
            
            # Open image
            img = Image.open(io.BytesIO(input_image_bytes))
            
            # Convert to RGBA if needed (for transparency)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create transparent overlay
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Calculate font size based on image dimensions
            font_size = min(img.size) // 10
            
            try:
                # Try to use a better font if available
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
            
            # Get text size
            text = config['text']
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position (center)
            x = (img.size[0] - text_width) // 2
            y = (img.size[1] - text_height) // 2
            
            # Calculate opacity
            opacity = int(config['opacity'] * 255)
            
            # Draw watermark
            draw.text(
                (x, y),
                text,
                fill=(*config['color'], opacity),
                font=font
            )
            
            # Composite the watermark onto the original image
            watermarked = Image.alpha_composite(img, overlay)
            
            # Convert back to original format if needed
            if image_format.upper() == 'JPEG' or image_format.upper() == 'JPG':
                watermarked = watermarked.convert('RGB')
            
            # Save to bytes
            output_buffer = io.BytesIO()
            watermarked.save(output_buffer, format=image_format.upper())
            output_buffer.seek(0)
            
            logger.info(f"Added {classification} watermark to {image_format} image")
            return output_buffer.read()
            
        except Exception as e:
            logger.error(f"Failed to watermark image: {e}")
            return input_image_bytes
    
    @classmethod
    def watermark_file(cls, file_content, file_name, file_type, classification):
        """
        Smart watermarking that detects file type and applies appropriate watermark
        
        Args:
            file_content: bytes of the file
            file_name: str name of the file
            file_type: str MIME type
            classification: str classification level
            
        Returns:
            bytes: watermarked file (or original if watermarking not supported/needed)
        """
        if not cls.should_watermark(classification):
            logger.info(f"No watermark needed for {classification}")
            return file_content
        
        file_extension = file_name.lower().split('.')[-1]
        
        logger.info(f"Attempting to watermark {file_name} (type: {file_type}, classification: {classification})")
        
        # PDF files
        if file_extension == 'pdf' or 'pdf' in file_type.lower():
            return cls.add_watermark_to_pdf(file_content, classification)
        
        # Word documents
        elif file_extension in ['docx', 'doc'] or 'word' in file_type.lower():
            if file_extension == 'docx':
                return cls.add_watermark_to_docx(file_content, classification)
            else:
                logger.warning("Cannot watermark .doc files (old format), only .docx supported")
                return file_content
        
        # Image files
        elif file_extension in ['png', 'jpg', 'jpeg'] or 'image' in file_type.lower():
            image_format = file_extension.upper()
            if image_format == 'JPG':
                image_format = 'JPEG'
            return cls.add_watermark_to_image(file_content, classification, image_format)
        
        else:
            logger.info(f"Watermarking not supported for file type: {file_type}")
            return file_content


# Convenience functions for easy import
def watermark_document(file_content, file_name, file_type, classification):
    """Convenience wrapper for DocumentWatermarker.watermark_file"""
    return DocumentWatermarker.watermark_file(file_content, file_name, file_type, classification)