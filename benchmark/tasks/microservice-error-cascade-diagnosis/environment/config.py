"""Application configuration for ProfileHub."""

import os

APP_NAME = 'ProfileHub'
APP_VERSION = '2.4.1'
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))
DB_NAME = os.environ.get('DB_NAME', 'profilehub')
DB_USER = os.environ.get('DB_USER', 'app_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'p@ss#word!$')

SESSION_TTL_SECONDS = 3600
MAX_LOGIN_ATTEMPTS = 5
TOKEN_PREFIX = 'phub_'


def get_connection_string() -> str:
    """Buggy: password is inserted raw and breaks URI parsing for special chars."""
    return f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
