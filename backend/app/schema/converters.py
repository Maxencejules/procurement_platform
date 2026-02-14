"""Convert SQLAlchemy models to Strawberry types."""
from app.models.approval import ApprovalDecision, ApprovalPolicy, ApprovalStep, PolicyRule
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.purchase_request import PurchaseRequest
from app.models.user import User
from app.schema.types import (
    ApprovalDecisionType, ApprovalPolicyType, ApprovalStepType, AuditLogType,
    OrganizationType, PolicyRuleType, PurchaseRequestType, UserType,
)


def to_user_type(u: User) -> UserType:
    return UserType(
        id=str(u.id), email=u.email, full_name=u.full_name,
        role=u.role.value, org_id=str(u.org_id), created_at=u.created_at,
    )


def to_org_type(o: Organization) -> OrganizationType:
    return OrganizationType(id=str(o.id), name=o.name, slug=o.slug, created_at=o.created_at)


def to_rule_type(r: PolicyRule) -> PolicyRuleType:
    return PolicyRuleType(id=str(r.id), field=r.field, operator=r.operator, value=r.value)


def to_policy_type(p: ApprovalPolicy) -> ApprovalPolicyType:
    return ApprovalPolicyType(
        id=str(p.id), name=p.name, description=p.description,
        approver_id=str(p.approver_id),
        approver=to_user_type(p.approver) if p.approver else None,
        priority=p.priority, is_active=p.is_active,
        rules=[to_rule_type(r) for r in (p.rules or [])],
        created_at=p.created_at,
    )


def to_decision_type(d: ApprovalDecision | None) -> ApprovalDecisionType | None:
    if not d:
        return None
    return ApprovalDecisionType(
        id=str(d.id), decision=d.decision.value, comments=d.comments,
        decided_by=str(d.decided_by),
        decider=to_user_type(d.decider) if d.decider else None,
        decided_at=d.decided_at,
    )


def to_step_type(s: ApprovalStep, include_request: bool = False) -> ApprovalStepType:
    pr = None
    if include_request and s.purchase_request:
        pr = to_request_type(s.purchase_request)
    return ApprovalStepType(
        id=str(s.id), policy_id=str(s.policy_id),
        policy=to_policy_type(s.policy) if s.policy else None,
        approver_id=str(s.approver_id),
        approver=to_user_type(s.approver) if s.approver else None,
        step_order=s.step_order, status=s.status,
        decision=to_decision_type(s.decision),
        purchase_request=pr,
        created_at=s.created_at,
    )


def to_request_type(r: PurchaseRequest) -> PurchaseRequestType:
    return PurchaseRequestType(
        id=str(r.id), title=r.title, description=r.description,
        vendor=r.vendor, amount=float(r.amount), category=r.category,
        cost_center=r.cost_center, status=r.status.value,
        requester_id=str(r.requester_id),
        requester=to_user_type(r.requester) if r.requester else None,
        org_id=str(r.org_id),
        approval_steps=[to_step_type(s) for s in (r.approval_steps or [])],
        created_at=r.created_at, updated_at=r.updated_at,
        submitted_at=r.submitted_at, approved_at=r.approved_at,
        rejected_at=r.rejected_at,
    )


def to_audit_type(a: AuditLog) -> AuditLogType:
    return AuditLogType(
        id=str(a.id), entity_type=a.entity_type, entity_id=str(a.entity_id),
        action=a.action, old_value=a.old_value, new_value=a.new_value,
        performed_by=str(a.performed_by),
        performer=to_user_type(a.performer) if a.performer else None,
        org_id=str(a.org_id), created_at=a.created_at,
    )
