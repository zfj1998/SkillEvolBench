def infer_region_phrase(query):
    if "california" in query.lower():
        return "California"
    return None


def infer_sort_clause(query):
    if "amount descending" in query.lower():
        return "amount descending"
    return None
