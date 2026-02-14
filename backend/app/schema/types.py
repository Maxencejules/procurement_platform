import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import strawberry


@strawberry.type
class OrganizationType:
    id: strawberry.ID
    name: str
    slug: str
    created_at: datetime


@strawberry.type
class UserType:
    id: strawberry.ID
    email: str
    full_name: str
    role: str
    org_id: strawberry.ID
    created_at: datetime


@strawberry.type
class PolicyRuleType:
    id: strawberry.ID
    field: str
    operator: str
    value: str


@strawberry.type
class ApprovalPolicyType:
    id: strawberry.ID
    name: str
    description: Optional[str]
    approver_id: strawberry.ID
    approver: Optional[UserType]
    priority: int
    is_active: bool
    rules: list[PolicyRuleType]
    created_at: datetime


@strawberry.type
class ApprovalDecisionType:
    id: strawberry.ID
    decision: str
    comments: Optional[str]
    decided_by: strawberry.ID
    decider: Optional[UserType]
    decided_at: datetime


@strawberry.type
class ApprovalStepType:
    id: strawberry.ID
    policy_id: strawberry.ID
    policy: Optional[ApprovalPolicyType]
    approver_id: strawberry.ID
    approver: Optional[UserType]
    step_order: int
    status: str
    decision: Optional[ApprovalDecisionType]
    created_at: datetime


@strawberry.type
class PurchaseRequestType:
    id: strawberry.ID
    title: str
    description: Optional[str]
    vendor: str
    amount: float
    category: str
    cost_center: str
    status: str
    requester_id: strawberry.ID
    requester: Optional[UserType]
    org_id: strawberry.ID
    approval_steps: list[ApprovalStepType]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]


@strawberry.type
class AuditLogType:
    id: strawberry.ID
    entity_type: str
    entity_id: strawberry.ID
    action: str
    old_value: Optional[str]
    new_value: Optional[str]
    performed_by: strawberry.ID
    performer: Optional[UserType]
    org_id: strawberry.ID
    created_at: datetime


@strawberry.type
class PaginatedRequests:
    items: list[PurchaseRequestType]
    total: int
    page: int
    page_size: int


@strawberry.type
class PaginatedAuditLogs:
    items: list[AuditLogType]
    total: int
    page: int
    page_size: int


@strawberry.type
class AuthPayload:
    token: str
    user: UserType


@strawberry.type
class CycleTimeReport:
    status: str
    avg_hours: float
    count: int


@strawberry.type
class CategoryReport:
    category: str
    count: int
    total_amount: float


@strawberry.type
class BottleneckReport:
    approver_name: str
    approver_id: strawberry.ID
    pending_count: int
    avg_decision_hours: Optional[float]


# Input types
@strawberry.input
class CreateRequestInput:
    title: str
    description: Optional[str] = None
    vendor: str
    amount: float
    category: str
    cost_center: str


@strawberry.input
class UpdateRequestInput:
    title: Optional[str] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    cost_center: Optional[str] = None


@strawberry.input
class PolicyRuleInput:
    field: str
    operator: str
    value: str


@strawberry.input
class CreatePolicyInput:
    name: str
    description: Optional[str] = None
    approver_id: strawberry.ID
    priority: int = 0
    rules: list[PolicyRuleInput] = strawberry.field(default_factory=list)


@strawberry.input
class UpdatePolicyInput:
    name: Optional[str] = None
    description: Optional[str] = None
    approver_id: Optional[strawberry.ID] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    rules: Optional[list[PolicyRuleInput]] = None
