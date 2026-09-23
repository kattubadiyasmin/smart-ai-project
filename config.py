import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-study-secure-key-2026-production')
    
    # Database
    DATABASE_PATH = os.environ.get(
        'DATABASE_PATH', str(BASE_DIR / 'database' / 'smart_study.db')
    )
    
    # Uploads & Storage
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER', str(BASE_DIR / 'uploads')
    )
    GENERATED_PDF_FOLDER = os.environ.get(
        'GENERATED_PDF_FOLDER', str(BASE_DIR / 'generated_pdfs')
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # AI / Groq API
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
    GROQ_MODEL = os.environ.get('GROQ_MODEL', 'qwen/qwen3.8-27b')
    
    # Session Configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Set to True when SSL/HTTPS is enabled
