<<<<<<< HEAD
from utils import process_data
=======
from utils import helper_func
>>>>>>> feature/add-mode-param


def handle_request(request_data):
    """Handle incoming request."""
<<<<<<< HEAD
    result = process_data(request_data.get("items", []))
=======
    mode = request_data.get("mode", "default")
    result = helper_func(request_data.get("items", []), mode=mode)
>>>>>>> feature/add-mode-param
    return {"status": "ok", "processed": result, "count": len(result)}


def handle_batch_request(batch_data):
    """Handle batch request."""
    results = []
    for req in batch_data:
<<<<<<< HEAD
        results.append(process_data(req.get("items", [])))
=======
        mode = req.get("mode", "default")
        results.append(helper_func(req.get("items", []), mode=mode))
>>>>>>> feature/add-mode-param
    return {"status": "ok", "batches": results}
