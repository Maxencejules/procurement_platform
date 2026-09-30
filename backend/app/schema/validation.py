from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.errors import WorkflowError


def identifier(value) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise WorkflowError("Invalid identifier", "BAD_USER_INPUT") from error


def money(value, *, allow_zero=False) -> Decimal:
    try:
        amount = Decimal(str(value))
        if (not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero)
                or amount > Decimal("9999999999.99")
                or amount != amount.quantize(Decimal("0.01"))):
            raise InvalidOperation
    except (InvalidOperation, ValueError) as error:
        raise WorkflowError(
            "Amount must be finite, positive, within 9999999999.99 and have at most two decimal places",
            "BAD_USER_INPUT",
        ) from error
    return amount


def required_text(value: str, field: str, limit: int) -> str:
    value = value.strip()
    if not value or len(value) > limit:
        raise WorkflowError(f"{field} must contain 1 to {limit} characters", "BAD_USER_INPUT")
    return value


def policy_rules(rules) -> None:
    for rule in rules:
        rule.value = required_text(rule.value, "Rule value", 255)
        if rule.field == "amount" and rule.operator in {"gt", "gte", "lt", "lte", "eq"}:
            money(rule.value, allow_zero=True)
        elif rule.field in {"category", "cost_center", "vendor"} and rule.operator in {"eq", "in"}:
            if any(not part.strip() for part in rule.value.split(",")):
                raise WorkflowError("Rule values cannot be empty", "BAD_USER_INPUT")
        else:
            raise WorkflowError("Unsupported policy field or operator", "BAD_USER_INPUT")
