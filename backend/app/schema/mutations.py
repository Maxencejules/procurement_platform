from decimal import Decimal
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


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def login(self, info: Info, email: str, password: str) -> AuthPayload:
        session: AsyncSession = info.context["session"]
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        token = create_access_token(user.id, user.org_id, user.role.value)
        return AuthPayload(token=token, user=to_user_type(user))

    @strawberry.mutation
    async def create_purchase_request(self, info: Info, input: CreateRequestInput) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = PurchaseRequest(
            title=input.title,
            description=input.description,
            vendor=input.vendor,
            amount=Decimal(str(input.amount)),
            category=input.category,
            cost_center=input.cost_center,
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
        await session.commit()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    async def update_purchase_request(
        self, info: Info, id: strawberry.ID, input: UpdateRequestInput
    ) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await session.get(PurchaseRequest, UUID(str(id)))
        if not pr or str(pr.org_id) != auth.org_id:
            raise ValueError("Not found")
        if pr.status != RequestStatus.DRAFT:
            raise ValueError("Can only edit draft requests")

        for field in ["title", "description", "vendor", "category", "cost_center"]:
            val = getattr(input, field, None)
            if val is not None:
                setattr(pr, field, val)
        if input.amount is not None:
            pr.amount = Decimal(str(input.amount))

        await session.commit()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    async def submit_request(self, info: Info, id: strawberry.ID) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await session.get(PurchaseRequest, UUID(str(id)))
        if not pr or str(pr.org_id) != auth.org_id:
            raise ValueError("Not found")

        await transition_status(session, pr, RequestStatus.SUBMITTED, UUID(auth.user_id))
        await route_approval(session, pr, UUID(auth.user_id))
        await session.commit()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    async def cancel_request(self, info: Info, id: strawberry.ID) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await session.get(PurchaseRequest, UUID(str(id)))
        if not pr or str(pr.org_id) != auth.org_id:
            raise ValueError("Not found")

        await transition_status(session, pr, RequestStatus.CANCELLED, UUID(auth.user_id))
        await session.commit()
        await session.refresh(pr)
        return to_request_type(pr)

    @strawberry.mutation
    async def approve_step(
        self, info: Info, step_id: strawberry.ID, comments: str | None = None
    ) -> ApprovalStepType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        step = await session.get(ApprovalStep, UUID(str(step_id)))
        if not step or str(step.approver_id) != auth.user_id:
            raise ValueError("Not found or not authorized")
        if step.status != "pending":
            raise ValueError("Step already decided")

        await process_decision(session, step, DecisionType.APPROVED, UUID(auth.user_id), comments)
        await session.commit()
        await session.refresh(step)
        return to_step_type(step)

    @strawberry.mutation
    async def reject_step(
        self, info: Info, step_id: strawberry.ID, comments: str | None = None
    ) -> ApprovalStepType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        step = await session.get(ApprovalStep, UUID(str(step_id)))
        if not step or str(step.approver_id) != auth.user_id:
            raise ValueError("Not found or not authorized")
        if step.status != "pending":
            raise ValueError("Step already decided")

        await process_decision(session, step, DecisionType.REJECTED, UUID(auth.user_id), comments)
        await session.commit()
        await session.refresh(step)
        return to_step_type(step)

    @strawberry.mutation
    async def create_approval_policy(self, info: Info, input: CreatePolicyInput) -> ApprovalPolicyType:
        auth = get_auth_context(info)
        if auth.role != Role.ADMIN.value:
            raise PermissionError("Admin only")
        session: AsyncSession = info.context["session"]

        policy = ApprovalPolicy(
            name=input.name,
            description=input.description,
            org_id=UUID(auth.org_id),
            approver_id=UUID(str(input.approver_id)),
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
        await session.commit()
        await session.refresh(policy)
        return to_policy_type(policy)

    @strawberry.mutation
    async def update_approval_policy(
        self, info: Info, id: strawberry.ID, input: UpdatePolicyInput
    ) -> ApprovalPolicyType:
        auth = get_auth_context(info)
        if auth.role != Role.ADMIN.value:
            raise PermissionError("Admin only")
        session: AsyncSession = info.context["session"]

        policy = await session.get(ApprovalPolicy, UUID(str(id)))
        if not policy or str(policy.org_id) != auth.org_id:
            raise ValueError("Not found")

        for field in ["name", "description", "priority", "is_active"]:
            val = getattr(input, field, None)
            if val is not None:
                setattr(policy, field, val)
        if input.approver_id is not None:
            policy.approver_id = UUID(str(input.approver_id))

        if input.rules is not None:
            # Replace all rules
            for old_rule in list(policy.rules):
                await session.delete(old_rule)
            await session.flush()
            for r in input.rules:
                rule = PolicyRule(policy_id=policy.id, field=r.field, operator=r.operator, value=r.value)
                session.add(rule)

        await session.commit()
        await session.refresh(policy)
        return to_policy_type(policy)

    @strawberry.mutation
    async def delete_approval_policy(self, info: Info, id: strawberry.ID) -> bool:
        auth = get_auth_context(info)
        if auth.role != Role.ADMIN.value:
            raise PermissionError("Admin only")
        session: AsyncSession = info.context["session"]
        policy = await session.get(ApprovalPolicy, UUID(str(id)))
        if not policy or str(policy.org_id) != auth.org_id:
            raise ValueError("Not found")
        await session.delete(policy)
        await session.commit()
        return True
