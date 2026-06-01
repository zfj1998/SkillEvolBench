def existing_usernames(created):
    return set(created)


def freeze_username_snapshot(created):
    return set(created)


def username_is_duplicate(username, snapshot):
    return username in snapshot
