def build_local_error(error):
    return {
        "field": error["field"],
        "message": error["message"],
        "source": "local-validation",
    }
