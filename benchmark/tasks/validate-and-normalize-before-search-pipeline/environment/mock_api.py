TRACE = []

SALES = [
    {"region_code": "CA", "amount": 300, "date": "2025-03-02", "rep": "A"},
    {"region_code": "CA", "amount": 200, "date": "2025-03-20", "rep": "B"},
    {"region_code": "CA", "amount": 100, "date": "2025-03-25", "rep": "C"},
    {"region_code": "NV", "amount": 500, "date": "2025-03-25", "rep": "Z"}
]


def search_sales(params):
    TRACE.append(params)
    rows = [
        item
        for item in SALES
        if item["region_code"] == params["region_code"]
        and params["start_date"] <= item["date"] <= params["end_date"]
    ]
    if params["sort_by"] == "amount":
        reverse = params["sort_order"] == "desc"
        rows = sorted(rows, key=lambda item: item["amount"], reverse=reverse)
    return rows
