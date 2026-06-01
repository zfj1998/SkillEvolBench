"""Application configuration."""
import os

WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'whsec_test_secret_do_not_use_in_prod')
