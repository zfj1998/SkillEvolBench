"""Resolver presentation helpers.

This file mirrors how other services prepare Python dicts before GraphQL field
selection happens.
"""


def present_user_for_graphql(user):
    return {
        "id": user["id"],
        "user_name": user["user_name"],
        "email_address": user["email_address"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "created_at": user["created_at"],
    }
