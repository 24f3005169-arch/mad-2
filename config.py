import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', f"sqlite:///{BASE_DIR / 'instance' / 'tma.sqlite3'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_FROM = os.getenv('SMTP_FROM', 'noreply@tma.local')
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@tma.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
