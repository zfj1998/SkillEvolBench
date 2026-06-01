def build_rep_leaderboard(rows):
    return sorted(rows, key=lambda item: item.get("rep", ""))
