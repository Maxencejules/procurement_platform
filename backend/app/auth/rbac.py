from functools import wraps
from uuid import UUID

import strawberry
from strawberry.types import Info

from app.models.user import Role


@strawberry.type
class AuthContext:
    user_id: str
    org_id: str
    role: str

    @property
    def user_uuid(self) -> UUID:
        return UUID(self.user_id)

    @property
    def org_uuid(self) -> UUID:
        return UUID(self.org_id)

    def has_role(self, *roles: Role) -> bool:
        return self.role in [r.value for r in roles]


def get_auth_context(info: Info) -> AuthContext:
    ctx = info.context.get("auth")
    if not ctx:
        raise PermissionError("Authentication required")
    return ctx


def require_roles(*roles: Role):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            info = None
            for arg in args:
                if isinstance(arg, Info):
                    info = arg
                    break
            if info is None:
                for v in kwargs.values():
                    if isinstance(v, Info):
                        info = v
                        break
            if info is None:
                raise PermissionError("Cannot determine auth context")
            auth = get_auth_context(info)
            if not auth.has_role(*roles):
                raise PermissionError(f"Requires role: {', '.join(r.value for r in roles)}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
