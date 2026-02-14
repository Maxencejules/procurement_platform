from typing import Optional
from uuid import UUID

import strawberry
from sqlalchemy import select, func, distinct, extract
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.auth.rbac import get_auth_context, require_roles
from app.models.approval import ApprovalPolicy, ApprovalStep, ApprovalDecision
from app.models.audit_log import AuditLog
from app.models.purchase_request import PurchaseRequest, RequestStatus
from app.models.user import Role, User
from app.schema.converters import (
    to_request_type, to_audit_type, to_policy_type, to_user_type, to_step_type,
)
from app.schema.types import (
    PaginatedRequests, PaginatedAuditLogs, ApprovalPolicyType, ApprovalStepType,
    UserType, PurchaseRequestType, CycleTimeReport, CategoryReport, BottleneckReport,
)


@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> UserType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        user = await session.get(User, UUID(auth.user_id))
        if not user:
            raise ValueError("User not found")
        return to_user_type(user)

    @strawberry.field
    async def users(self, info: Info) -> list[UserType]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        result = await session.execute(
            select(User).where(User.org_id == UUID(auth.org_id))
        )
        return [to_user_type(u) for u in result.scalars().all()]

    @strawberry.field
    async def purchase_requests(
        self, info: Info,
        page: int = 1, page_size: int = 20,
        status: Optional[str] = None,
        category: Optional[str] = None,
        cost_center: Optional[str] = None,
    ) -> PaginatedRequests:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        query = select(PurchaseRequest).where(PurchaseRequest.org_id == UUID(auth.org_id))

        if status:
            query = query.where(PurchaseRequest.status == RequestStatus(status))
        if category:
            query = query.where(PurchaseRequest.category == category)
        if cost_center:
            query = query.where(PurchaseRequest.cost_center == cost_center)

        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        query = query.order_by(PurchaseRequest.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        items = [to_request_type(r) for r in result.scalars().all()]
        return PaginatedRequests(items=items, total=total, page=page, page_size=page_size)

    @strawberry.field
    async def purchase_request(self, info: Info, id: strawberry.ID) -> PurchaseRequestType:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        pr = await session.get(PurchaseRequest, UUID(str(id)))
        if not pr or str(pr.org_id) != auth.org_id:
            raise ValueError("Request not found")
        return to_request_type(pr)

    @strawberry.field
    async def approval_inbox(self, info: Info) -> list[ApprovalStepType]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        result = await session.execute(
            select(ApprovalStep)
            .join(PurchaseRequest)
            .where(
                ApprovalStep.approver_id == UUID(auth.user_id),
                ApprovalStep.status == "pending",
                PurchaseRequest.org_id == UUID(auth.org_id),
            )
            .order_by(ApprovalStep.created_at.desc())
        )
        return [to_step_type(s, include_request=True) for s in result.scalars().all()]

    @strawberry.field
    async def approval_policies(self, info: Info) -> list[ApprovalPolicyType]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        result = await session.execute(
            select(ApprovalPolicy).where(ApprovalPolicy.org_id == UUID(auth.org_id))
            .order_by(ApprovalPolicy.priority)
        )
        return [to_policy_type(p) for p in result.scalars().all()]

    @strawberry.field
    async def audit_logs(
        self, info: Info,
        entity_id: Optional[strawberry.ID] = None,
        page: int = 1, page_size: int = 50,
    ) -> PaginatedAuditLogs:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        query = select(AuditLog).where(AuditLog.org_id == UUID(auth.org_id))
        if entity_id:
            query = query.where(AuditLog.entity_id == UUID(str(entity_id)))
        count_q = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_q)).scalar() or 0
        query = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        items = [to_audit_type(a) for a in result.scalars().all()]
        return PaginatedAuditLogs(items=items, total=total, page=page, page_size=page_size)

    # --- Reporting ---
    @strawberry.field
    async def cycle_time_report(self, info: Info) -> list[CycleTimeReport]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        # Compute avg time between consecutive status changes
        result = await session.execute(
            select(
                AuditLog.new_value,
                func.count(AuditLog.id).label("cnt"),
            )
            .where(
                AuditLog.org_id == UUID(auth.org_id),
                AuditLog.entity_type == "PurchaseRequest",
                AuditLog.action == "status_change",
            )
            .group_by(AuditLog.new_value)
        )
        reports = []
        for row in result.all():
            # Get avg time for transitions to this status
            sub = await session.execute(
                select(func.avg(
                    extract("epoch", AuditLog.created_at) -
                    extract("epoch", PurchaseRequest.created_at)
                ))
                .join(PurchaseRequest, PurchaseRequest.id == AuditLog.entity_id)
                .where(
                    AuditLog.org_id == UUID(auth.org_id),
                    AuditLog.new_value == row[0],
                    AuditLog.action == "status_change",
                )
            )
            avg_seconds = sub.scalar() or 0
            reports.append(CycleTimeReport(
                status=row[0], avg_hours=round(avg_seconds / 3600, 2), count=row[1]
            ))
        return reports

    @strawberry.field
    async def category_report(self, info: Info) -> list[CategoryReport]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        result = await session.execute(
            select(
                PurchaseRequest.category,
                func.count(PurchaseRequest.id),
                func.sum(PurchaseRequest.amount),
            )
            .where(PurchaseRequest.org_id == UUID(auth.org_id))
            .group_by(PurchaseRequest.category)
        )
        return [
            CategoryReport(category=row[0], count=row[1], total_amount=float(row[2] or 0))
            for row in result.all()
        ]

    @strawberry.field
    async def bottleneck_report(self, info: Info) -> list[BottleneckReport]:
        auth = get_auth_context(info)
        session: AsyncSession = info.context["session"]
        # Count pending steps per approver
        result = await session.execute(
            select(
                User.id,
                User.full_name,
                func.count(ApprovalStep.id).label("pending"),
            )
            .join(ApprovalStep, ApprovalStep.approver_id == User.id)
            .join(PurchaseRequest, PurchaseRequest.id == ApprovalStep.purchase_request_id)
            .where(
                PurchaseRequest.org_id == UUID(auth.org_id),
                ApprovalStep.status == "pending",
            )
            .group_by(User.id, User.full_name)
            .order_by(func.count(ApprovalStep.id).desc())
        )
        reports = []
        for row in result.all():
            # Get avg decision time for this approver
            avg_q = await session.execute(
                select(func.avg(
                    extract("epoch", ApprovalDecision.decided_at) -
                    extract("epoch", ApprovalStep.created_at)
                ))
                .join(ApprovalStep, ApprovalStep.id == ApprovalDecision.step_id)
                .where(ApprovalDecision.decided_by == row[0])
            )
            avg_s = avg_q.scalar()
            reports.append(BottleneckReport(
                approver_name=row[1], approver_id=str(row[0]),
                pending_count=row[2],
                avg_decision_hours=round(avg_s / 3600, 2) if avg_s else None,
            ))
        return reports
