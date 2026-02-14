"""Rules-based approval routing engine.

Evaluates approval policies against purchase requests to determine
which approval steps are needed, then manages the approval flow.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalPolicy, ApprovalStep, ApprovalDecision, DecisionType, PolicyRule
from app.models.audit_log import AuditLog
from app.models.purchase_request import PurchaseRequest, RequestStatus, VALID_TRANSITIONS


def evaluate_rule(rule: PolicyRule, request: PurchaseRequest) -> bool:
    """Check if a single rule matches a purchase request."""
    field_value = getattr(request, rule.field, None)
    if field_value is None:
        return False

    if rule.field == "amount":
        threshold = Decimal(rule.value)
        amount = Decimal(str(field_value))
        ops = {"gt": amount > threshold, "gte": amount >= threshold,
               "lt": amount < threshold, "lte": amount <= threshold, "eq": amount == threshold}
        return ops.get(rule.operator, False)

    if rule.operator == "eq":
        return str(field_value).lower() == rule.value.lower()
    if rule.operator == "in":
        allowed = [v.strip().lower() for v in rule.value.split(",")]
        return str(field_value).lower() in allowed

    return False


def matches_policy(policy: ApprovalPolicy, request: PurchaseRequest) -> bool:
    """A policy matches if ALL its rules match (AND logic)."""
    if not policy.rules:
        return True  # No rules = matches everything
    return all(evaluate_rule(rule, request) for rule in policy.rules)


async def route_approval(session: AsyncSession, request: PurchaseRequest, user_id: uuid.UUID) -> list[ApprovalStep]:
    """Find matching policies and create approval steps for a purchase request."""
    result = await session.execute(
        select(ApprovalPolicy)
        .where(ApprovalPolicy.org_id == request.org_id, ApprovalPolicy.is_active == True)
        .order_by(ApprovalPolicy.priority)
    )
    policies = result.scalars().all()

    matching = [p for p in policies if matches_policy(p, request)]

    if not matching:
        # Auto-approve if no policies match
        await transition_status(session, request, RequestStatus.APPROVED, user_id)
        return []

    steps = []
    for i, policy in enumerate(matching):
        step = ApprovalStep(
            purchase_request_id=request.id,
            policy_id=policy.id,
            approver_id=policy.approver_id,
            step_order=i + 1,
            status="pending",
        )
        session.add(step)
        steps.append(step)

    await transition_status(session, request, RequestStatus.PENDING_APPROVAL, user_id)
    return steps


async def process_decision(
    session: AsyncSession,
    step: ApprovalStep,
    decision: DecisionType,
    user_id: uuid.UUID,
    comments: str | None = None,
) -> PurchaseRequest:
    """Record an approval decision and advance the workflow."""
    approval_decision = ApprovalDecision(
        step_id=step.id,
        decision=decision,
        comments=comments,
        decided_by=user_id,
    )
    session.add(approval_decision)
    step.status = decision.value

    # Explicitly load the purchase request and sibling steps
    request = await session.get(PurchaseRequest, step.purchase_request_id)
    sibling_result = await session.execute(
        select(ApprovalStep).where(ApprovalStep.purchase_request_id == request.id)
    )
    all_steps = sibling_result.scalars().all()

    if decision == DecisionType.REJECTED:
        await transition_status(session, request, RequestStatus.REJECTED, user_id)
        # Mark remaining pending steps as skipped
        for s in all_steps:
            if s.status == "pending" and s.id != step.id:
                s.status = "skipped"
    elif decision == DecisionType.APPROVED:
        pending_steps = [s for s in all_steps if s.status == "pending" and s.id != step.id]
        if not pending_steps:
            await transition_status(session, request, RequestStatus.APPROVED, user_id)

    await session.flush()
    return request


async def transition_status(
    session: AsyncSession,
    request: PurchaseRequest,
    new_status: RequestStatus,
    user_id: uuid.UUID,
) -> None:
    """Validate and perform a status transition, creating an audit log entry."""
    old_status = request.status
    allowed = VALID_TRANSITIONS.get(old_status, set())

    if new_status not in allowed:
        raise ValueError(f"Invalid transition from {old_status.value} to {new_status.value}")

    request.status = new_status
    now = datetime.now(timezone.utc)

    if new_status == RequestStatus.SUBMITTED:
        request.submitted_at = now
    elif new_status == RequestStatus.APPROVED:
        request.approved_at = now
    elif new_status == RequestStatus.REJECTED:
        request.rejected_at = now

    audit = AuditLog(
        entity_type="PurchaseRequest",
        entity_id=request.id,
        action="status_change",
        old_value=old_status.value,
        new_value=new_status.value,
        performed_by=user_id,
        org_id=request.org_id,
    )
    session.add(audit)
    await session.flush()
