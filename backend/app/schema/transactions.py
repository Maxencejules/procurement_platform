from functools import wraps

from graphql import GraphQLError
from sqlalchemy.exc import IntegrityError

from app.errors import WorkflowError


def transactional(resolver):
    """One transaction per mutation field, including its audit records.

    Convert the result before committing, so serialization/loading failures also
    roll back. GraphQL catches resolver exceptions; it does not roll back a session.
    """
    @wraps(resolver)
    async def wrapper(self, info, *args, **kwargs):
        session = info.context["session"]
        try:
            result = await resolver(self, info, *args, **kwargs)
            await session.commit()
            return result
        except WorkflowError as error:
            await session.rollback()
            raise GraphQLError(str(error), extensions={"code": error.code}) from error
        except IntegrityError as error:
            await session.rollback()
            raise GraphQLError(
                "Write conflicts with existing data", extensions={"code": "CONFLICT"}
            ) from error
        except BaseException:
            await session.rollback()
            raise

    return wrapper
