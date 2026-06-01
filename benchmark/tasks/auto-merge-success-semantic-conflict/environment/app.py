"""Application that uses validators."""
from validators import validate_input, validate_name, validate_age


def register_user(name, email, phone, age):
    """Register a new user with validation."""
    errors = []

    name_result = validate_name(name)
    if not name_result["valid"]:
        errors.append(f"Name: {name_result['error']}")

    # Validates email using validate_input
    email_result = validate_input(email)
    if not email_result["valid"]:
        errors.append(f"Email: {email_result['error']}")

    # Also validates phone using validate_input
    phone_result = validate_input(phone)
    if not phone_result["valid"]:
        errors.append(f"Phone: {phone_result['error']}")

    age_result = validate_age(age)
    if not age_result["valid"]:
        errors.append(f"Age: {age_result['error']}")

    if errors:
        return {"success": False, "errors": errors}
    return {"success": True, "message": "User registered successfully"}
