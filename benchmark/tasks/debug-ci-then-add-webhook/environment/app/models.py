"""Data models for EventHub."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class UserResponseSchema:
    """Canonical API-facing user schema after the v3.2 refactor."""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str

    def to_api_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'display_name': self.username,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at,
        }

    @classmethod
    def from_record(cls, row: Dict[str, Any]) -> 'UserResponseSchema':
        return cls(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            role=row.get('role', 'viewer'),
            is_active=row.get('is_active', True),
            created_at=row.get('created_at', datetime.now().isoformat()),
        )


@dataclass
class WebhookEvent:
    event_id: str
    event_type: str
    payload: Dict[str, Any]
    received_at: str = field(default_factory=lambda: datetime.now().isoformat())
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_event_payload(data: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ['payload must be a JSON object']
    for req in ('event_id', 'event_type', 'data'):
        if req not in data:
            errors.append(f'missing required field: {req}')
    return errors
