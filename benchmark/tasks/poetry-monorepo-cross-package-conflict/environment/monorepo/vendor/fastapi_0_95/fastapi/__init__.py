__version__ = "0.95.0"


class FastAPI:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorator(func):
            self.routes[("POST", path)] = func
            return func
        return decorator
