def build_summary(rows, successes, failures):
    return {
        "total": len(rows),
        "succeeded": len(successes),
        "failed": len(failures),
    }
