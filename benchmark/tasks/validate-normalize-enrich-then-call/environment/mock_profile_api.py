PROFILES = {
  "u1": {"timezone": "America/New_York", "currency": "USD"},
  "u2": {"timezone": None, "currency": "EUR"},
  "u4": {"timezone": "Europe/Berlin", "currency": None}
}
TRACE = []


def get_profile(user_id):
    TRACE.append(user_id)
    if user_id not in PROFILES:
        raise KeyError(user_id)
    return PROFILES[user_id]
