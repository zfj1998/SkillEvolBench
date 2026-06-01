# Utility functions

<<<<<<< HEAD
def process_data(data):
    """Process the input data and return results."""
    if not data:
        return []
    cleaned = [item.strip() for item in data if item]
    return [item.upper() for item in cleaned]
=======
def helper_func(data, mode="default"):
    """Process the input data and return results.

    Args:
        data: Input data list
        mode: Processing mode - 'default', 'strict', or 'lenient'
    """
    if not data:
        return []
    cleaned = [item.strip() for item in data if item]
    if mode == "strict":
        cleaned = [item for item in cleaned if len(item) > 2]
    elif mode == "lenient":
        cleaned = [item if item else "N/A" for item in data]
    return [item.upper() for item in cleaned]
>>>>>>> feature/add-mode-param
