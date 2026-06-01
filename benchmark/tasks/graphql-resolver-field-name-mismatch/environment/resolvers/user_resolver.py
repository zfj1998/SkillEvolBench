"""User resolvers for GraphQL queries."""
from models.user import get_user_by_id, get_all_users
from resolvers.presenter import present_user_for_graphql


def resolve_user(_, info, id):
    """Resolve a single user query."""
    user = get_user_by_id(id)
    if not user:
        return None
    return present_user_for_graphql(user)


def resolve_users(_, info):
    """Resolve all users query."""
    users = get_all_users()
    return [present_user_for_graphql(u) for u in users]
