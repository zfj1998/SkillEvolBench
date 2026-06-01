<<<<<<< HEAD
from utils import process_data
=======
from utils import helper_func
>>>>>>> feature/add-mode-param


class DataService:
    def __init__(self):
        self.cache = {}

    def process(self, data, use_cache=True):
        """Process data with optional caching."""
        cache_key = str(data)
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]

<<<<<<< HEAD
        result = process_data(data)
=======
        result = helper_func(data, mode="strict")
>>>>>>> feature/add-mode-param

        if use_cache:
            self.cache[cache_key] = result
        return result
