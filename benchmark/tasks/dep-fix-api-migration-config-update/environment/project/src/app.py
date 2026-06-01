"""Application entry point."""
from alembic import run_upgrade
from database import engine

def initialize():
    return run_upgrade()

def get_db():
    return engine
