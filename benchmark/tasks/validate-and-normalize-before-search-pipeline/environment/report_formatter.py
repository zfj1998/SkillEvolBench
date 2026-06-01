def summarize_rows(rows):
    total = sum(item["amount"] for item in rows)
    average = total / len(rows)
    return {
        "count": len(rows),
        "total_amount": total,
        "average_amount": average,
        "rows": rows,
    }
