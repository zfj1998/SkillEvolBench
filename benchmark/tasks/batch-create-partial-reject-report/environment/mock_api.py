CREATED = []


def create_account(record):
    CREATED.append(record["username"])
    return {"id": len(CREATED), "username": record["username"]}
