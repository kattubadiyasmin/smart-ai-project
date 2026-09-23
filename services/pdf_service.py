import io
import re
import uuid
from pathlib import Path
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename
from config import Config

ALLOWED_EXTENSIONS = {"pdf"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_extracted_text(text):
    if not text:
        return ""
    # Normalize unicode spaces and clean carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace multiple horizontal spaces/tabs with a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace excessive consecutive newlines with two newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove null bytes or non-printable control characters (except tab/newline)
    text = "".join(ch for ch in text if ch in ("\n", "\t") or ord(ch) >= 32)
    return text.strip()

def process_and_extract_pdf(file_storage):
    """
    Saves an uploaded PDF file safely and extracts its clean text using PyPDF2.
    Returns:
        dict: {
            "success": True/False,
            "filename": original filename,
            "stored_filename": saved unique filename,
            "file_size": file size in bytes,
            "page_count": number of pages,
            "text": extracted and cleaned text,
            "error": error message if failed
        }
    """
    original_filename = file_storage.filename or "uploaded_study_material.pdf"
    if not allowed_file(original_filename):
        return {
            "success": False,
            "error": "Invalid file format. Only PDF (.pdf) documents are supported."
        }

    # Generate a unique, safe filename
    safe_base = secure_filename(original_filename)
    if not safe_base:
        safe_base = "document.pdf"
    unique_prefix = uuid.uuid4().hex[:10]
    stored_filename = f"{unique_prefix}_{safe_base}"
    
    upload_dir = Path(Config.UPLOAD_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination_path = upload_dir / stored_filename

    try:
        # Save file to disk
        file_storage.save(str(destination_path))
        file_size = destination_path.stat().st_size

        if file_size == 0:
            destination_path.unlink(missing_ok=True)
            return {
                "success": False,
                "error": "The uploaded PDF file is empty (0 bytes)."
            }

        # Check maximum allowed size
        if file_size > Config.MAX_CONTENT_LENGTH:
            destination_path.unlink(missing_ok=True)
            return {
                "success": False,
                "error": f"File is too large ({round(file_size / (1024 * 1024), 1)} MB). Maximum allowed size is 16 MB."
            }

        # Extract text using PyPDF2
        pages_text = []
        try:
            reader = PdfReader(str(destination_path))
            page_count = len(reader.pages)
            if page_count == 0:
                destination_path.unlink(missing_ok=True)
                return {
                    "success": False,
                    "error": "The uploaded PDF contains no pages."
                }

            for page_idx, page in enumerate(reader.pages):
                try:
                    p_text = page.extract_text()
                    if p_text:
                        pages_text.append(p_text)
                except Exception:
                    # Ignore single page extraction errors, continue with next
                    continue

        except Exception as e:
            destination_path.unlink(missing_ok=True)
            return {
                "success": False,
                "error": "Could not read this PDF. The file may be password protected or corrupted."
            }

        raw_text = "\n\n".join(pages_text)
        cleaned_text = clean_extracted_text(raw_text)

        # Check if text is readable or if it is a scanned image
        if len(cleaned_text) < 40:
            destination_path.unlink(missing_ok=True)
            return {
                "success": False,
                "error": "No readable text found in this PDF. It might be a scanned document or image-only PDF. Please upload a PDF with selectable text."
            }

        return {
            "success": True,
            "filename": original_filename,
            "stored_filename": stored_filename,
            "file_size": file_size,
            "page_count": page_count,
            "text": cleaned_text
        }

    except Exception as e:
        destination_path.unlink(missing_ok=True)
        return {
            "success": False,
            "error": "An unexpected error occurred while processing the PDF. Please try again."
        }
