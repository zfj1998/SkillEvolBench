def normalize_currency(record):
    if record["currency"] == "EUR":
        record = dict(record)
        record["amount"] = round(record["amount"] * 1.1, 2)
        record["currency"] = "USD"
    return record
