from uuid import UUID

import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.auth.jwt import hash_password, verify_password, create_access_token
from app.auth.rbac import get_auth_context
from app.models.approval import ApprovalPolicy, ApprovalStep, DecisionType, PolicyRule
from app.models.audit_log import AuditLog
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.models.user import User, Role
from app.schema.converters import to_request_type, to_policy_type, to_step_type, to_user_type
from app.schema.types import (
    AuthPayload, PurchaseRequestType, ApprovalPolicyType, ApprovalStepType,
    CreateRequestInput, UpdateRequestInput, CreatePolicyInput, UpdatePolicyInput,
)
from app.workflow.engine import route_approval, process_decision, transition_status
from app.errors import WorkflowError
from app.schema.transactions import transactional
from app.schema.validation import identifier, money, required_text, policy_rules


async def owned_request(session, auth, id):
    request = (await session.execute(
        select(PurchaseRequest)
        .where(PurchaseRequest.id == identifier(id), PurchaseRequest.org_id == auth.org_uuid)
        .with_for_update(of=PurchaseRequest)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if not request:
        raise WorkflowError("Request not found", "NOT_FOUND")
    if request.requester_id != auth.user_uuid and auth.role != Role.ADMIN.value:
        raise WorkflowError("Only the requester or an admin may change this request", "FORBIDDEN")
    return request


async def assigned_step(session, auth, id):
    if not auth.has_role(Role.APPROVER, Role.ADMIN):
        raise WorkflowError("Approver role required", "FORBIDDEN")
    step = (await session.execute(
        select(ApprovalStep).join(PurchaseRequest)
        .where(ApprovalStep.id == identifier(id), ApprovalStep.approver_id == auth.user_uuid,
               PurchaseRequest.org_id == auth.org_uuid)
    )).scalar_one_or_none()
    if not step:
        raise WorkflowError("Step not found", "NOT_FOUND")
    return step


async def policy_approver(session, auth, id):
    approver_id = identifier(id)
    user = (await session.execute(
        select(User).where(User.id == approver_id, User.org_id == auth.org_uuid,
                           User.role.in_([Role.APPROVER, Role.ADMIN]))
    )).scalar_one_or_none()
    if not user:
        raise WorkflowError("Approver must be an approver or admin in this organization", "BAD_USER_INPUT")
    return approver_id


async def admin_policy(session, auth, id):
    if auth.role != Role.ADMIN.value:
        raise WorkflowError("Admin only", "FORBIDDEN")
    policy = (await session.execute(
        select(ApprovalPolicy)
        .where(ApprovalPolicy.id == identifier(id), ApprovalPolicy.org_id == auth.org_uuid)
        .with_for_update(of=ApprovalPolicy).execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if not policy:
        raise WorkflowError("Policy not found", "NOT_FOUND")
    return policy


@strawberry.type
class Mutation:
    @strawberry.mutation
    @transactional
    async def login(self, info: Info, email: str, password: str) -> AuthPayload:
        session: AsyncSession = info.context["session"]
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise WorkflowError("Invalid credentials", "UNAUTHENTICATED")
        token = create_access_token(user.id, user.org_id, user.role.value)
        return AuthPayload(token=token, user=to_user_type(user))

    @strawberry.mutation
    @transactional
    async def create_purchase_request(self, info: Info, input: CreateRequestInput) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = PurchaseRequest(
            title=required_text(input.title, "Title", 255),
            description=input.description,
            vendor=required_text(input.vendor, "Vendor", 255),
            amount=money(input.amount),
            category=required_text(input.category, "Category", 100),
            cost_center=required_text(input.cost_center, "Cost center", 100),
            status=RequestStatus.DRAFT,
            requester_id=UUID(auth.user_id),
            org_id=UUID(auth.org_id),
        )
        session.add(pr)
        await session.flush()
        audit = AuditLog(
            entity_type="PurchaseRequest", entity_id=pr.id,
            action="created", new_value="draft",
            performed_by=UUID(auth.user_id), org_id=UUID(auth.org_id),
        )
        session.add(audit)
        await session.flush()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    @transactional
    async def update_purchase_request(
        self, info: Info, id: strawberry.ID, input: UpdateRequestInput
    ) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await owned_request(session, auth, id)
        if pr.status != RequestStatus.DRAFT:
            raise WorkflowError("Can only edit draft requests")

        for field in ["title", "description", "vendor", "category", "cost_center"]:
            val = getattr(input, field, None)
            if val is not None:
                if field != "description":
                    val = required_text(val, field, 255 if field in {"title", "vendor"} else 100)
                setattr(pr, field, val)
        if input.amount is not None:
            pr.amount = money(input.amount)

        await session.flush()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    @transactional
    async def submit_request(self, info: Info, id: strawberry.ID) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await owned_request(session, auth, id)

        await transition_status(session, pr, RequestStatus.SUBMITTED, UUID(auth.user_id))
        await route_approval(session, pr, UUID(auth.user_id))
        await session.flush()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    @transactional
    async def cancel_request(self, info: Info, id: strawberry.ID) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await owned_request(session, auth, id)

        await transition_status(session, pr, RequestStatus.CANCELLED, UUID(auth.user_id))
        for step in pr.approval_steps:
            if step.status == "pending":
                step.status = "skipped"
        await session.flush()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    @transactional
    async def approve_step(
        self, info: Info, step_id: strawberry.ID, comments: str | None = None
    ) -> ApprovalStepType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        step = await assigned_step(session, auth, step_id)

        await process_decision(session, step, DecisionType.APPROVED, UUID(auth.user_id), comments)
        await session.refresh(step)
        return to_step_type(step)

    @strawberry.mutation
    @transactional
    async def reject_step(
        self, info: Info, step_id: strawberry.ID, comments: str | None = None
    ) -> ApprovalStepType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        step = await assigned_step(session, auth, step_id)

        await process_decision(session, step, DecisionType.REJECTED, UUID(auth.user_id), comments)
        await session.refresh(step)
        return to_step_type(step)

    @strawberry.mutation
    @transactional
    async def create_approval_policy(self, info: Info, input: CreatePolicyInput) -> ApprovalPolicyType:
        auth = get_auth_context(info)
        if auth.role != Role.ADMIN.value:
            raise WorkflowError("Admin only", "FORBIDDEN")
        session: AsyncSession = info.context["session"]
        policy_rules(input.rules)
        approver_id = await policy_approver(session, auth, input.approver_id)

        policy = ApprovalPolicy(
            name=required_text(input.name, "Name", 255),
            description=input.description,
            org_id=UUID(auth.org_id),
            approver_id=approver_id,
            priority=input.priority,
        )
        session.add(policy)
        await session.flush()

        for r in input.rules:
            rule = PolicyRule(policy_id=policy.id, field=r.field, operator=r.operator, value=r.value)
            session.add(rule)

        audit = AuditLog(
            entity_type="ApprovalPolicy", entity_id=policy.id,
            action="created", new_value=policy.name,
            performed_by=UUID(auth.user_id), org_id=UUID(auth.org_id),
        )
        session.add(audit)
        await session.flush()
        await session.refresh(policy)
        return to_policy_type(policy)

    @strawberry.mutation
    @transactional
    async def update_approval_policy(
        self, info: Info, id: strawberry.ID, input: UpdatePolicyInput
    ) -> ApprovalPolicyType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        policy = await admin_policy(session, auth, id)
        if input.rules is not None:
            policy_rules(input.rules)

        for field in ["name", "description", "priority", "is_active"]:
            val = getattr(input, field, None)
            if val is not None:
                if field == "name":
                    val = required_text(val, "Name", 255)
                setattr(policy, field, val)
        if input.approver_id is not None:
            policy.approver_id = await policy_approver(session, auth, input.approver_id)

        if input.rules is not None:
            policy.rules = [PolicyRule(field=r.field, operator=r.operator, value=r.value)
                            for r in input.rules]

        await session.flush()
        await session.refresh(policy)
        return to_policy_type(policy)

    @strawberry.mutation
    @transactional
    async def delete_approval_policy(self, info: Info, id: strawberry.ID) -> bool:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        policy = await admin_policy(session, auth, id)
        await session.delete(policy)
        return True
