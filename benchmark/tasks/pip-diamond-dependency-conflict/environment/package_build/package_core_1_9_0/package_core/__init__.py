from package_data import process

def initialize(payload):
    result = process(payload, mode="legacy")
    return f"alpha:{result}"
