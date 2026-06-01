"""Input validation utilities."""
import re


# --- Added by Branch A (email validation feature) ---
def validate_input(value):
    """Validate email address format."""
    if not value or not isinstance(value, str):
        return {"valid": False, "error": "Empty or non-string input"}

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, value):
        return {"valid": True, "type": "email"}
    return {"valid": False, "error": "Invalid email format"}


def validate_name(value):
    """Validate a person's name."""
    if not value or not isinstance(value, str):
        return {"valid": False, "error": "Empty or non-string input"}
    if len(value) < 2:
        return {"valid": False, "error": "Name too short"}
    return {"valid": True, "type": "name"}


def validate_age(value):
    """Validate age."""
    if not isinstance(value, int) or value < 0 or value > 150:
        return {"valid": False, "error": "Invalid age"}
    return {"valid": True, "type": "age"}


# --- Added by Branch B (phone validation feature) ---
def validate_input(value):
    """Validate phone number format."""
    if not value or not isinstance(value, str):
        return {"valid": False, "error": "Empty or non-string input"}

    # Remove common formatting
    cleaned = value.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")

    if cleaned.isdigit() and 10 <= len(cleaned) <= 15:
        return {"valid": True, "type": "phone"}
    return {"valid": False, "error": "Invalid phone number format"}
