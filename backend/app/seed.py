"""Seed script to populate database with demo data."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.auth.jwt import hash_password
from app.database import async_session, engine, Base
from app.models import (
    Organization, User, Role, PurchaseRequest, RequestStatus,
    ApprovalPolicy, PolicyRule, ApprovalStep, ApprovalDecision, AuditLog,
)
from app.models.approval import DecisionType

import app.models  # noqa: F401


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(Organization))
        if result.scalar_one_or_none():
            print("Database already seeded.")
            return

        # Organization
        org = Organization(name="Acme Corp", slug="acme")
        session.add(org)
        await session.flush()

        # Users
        admin = User(
            email="admin@acme.com", password_hash=hash_password("admin123"),
            full_name="Alice Admin", role=Role.ADMIN, org_id=org.id,
        )
        approver = User(
            email="approver@acme.com", password_hash=hash_password("approver123"),
            full_name="Bob Approver", role=Role.APPROVER, org_id=org.id,
        )
        approver2 = User(
            email="approver2@acme.com", password_hash=hash_password("approver123"),
            full_name="Carol VP", role=Role.APPROVER, org_id=org.id,
        )
        requester = User(
            email="requester@acme.com", password_hash=hash_password("requester123"),
            full_name="Dave Requester", role=Role.REQUESTER, org_id=org.id,
        )
        for u in [admin, approver, approver2, requester]:
            session.add(u)
        await session.flush()

        # Approval Policies
        policy_low = ApprovalPolicy(
            name="Standard Approval (<$10k)",
            description="Single manager approval for requests under $10,000",
            org_id=org.id, approver_id=approver.id, priority=1, is_active=True,
        )
        session.add(policy_low)
        await session.flush()
        session.add(PolicyRule(policy_id=policy_low.id, field="amount", operator="lt", value="10000"))

        policy_high = ApprovalPolicy(
            name="VP Approval (>=$10k)",
            description="VP approval required for requests $10,000 and above",
            org_id=org.id, approver_id=approver2.id, priority=2, is_active=True,
        )
        session.add(policy_high)
        await session.flush()
        session.add(PolicyRule(policy_id=policy_high.id, field="amount", operator="gte", value="10000"))

        policy_it = ApprovalPolicy(
            name="IT Category Review",
            description="Additional review for IT purchases",
            org_id=org.id, approver_id=approver.id, priority=3, is_active=True,
        )
        session.add(policy_it)
        await session.flush()
        session.add(PolicyRule(policy_id=policy_it.id, field="category", operator="eq", value="IT"))

        # Sample purchase requests
        now = datetime.now(timezone.utc)
        categories = ["IT", "Office Supplies", "Marketing", "Facilities", "Professional Services"]
        cost_centers = ["ENG-001", "MKT-002", "OPS-003", "HR-004"]
        vendors = ["Dell Technologies", "Staples", "Google Ads", "WeWork", "Deloitte"]
        sample_requests = [
            ("New Laptops for Engineering", 25000, "IT", "ENG-001", "Dell Technologies", RequestStatus.APPROVED),
            ("Office Chairs", 3500, "Office Supplies", "OPS-003", "Staples", RequestStatus.APPROVED),
            ("Q3 Marketing Campaign", 15000, "Marketing", "MKT-002", "Google Ads", RequestStatus.PENDING_APPROVAL),
            ("Conference Room AV Setup", 8000, "Facilities", "OPS-003", "AV Solutions Inc", RequestStatus.PENDING_APPROVAL),
            ("Security Audit", 45000, "Professional Services", "ENG-001", "Deloitte", RequestStatus.SUBMITTED),
            ("Standing Desks", 2000, "Office Supplies", "HR-004", "Staples", RequestStatus.DRAFT),
            ("Cloud Infrastructure", 12000, "IT", "ENG-001", "AWS", RequestStatus.REJECTED),
            ("Team Offsite", 5000, "Marketing", "MKT-002", "Airbnb", RequestStatus.APPROVED),
        ]

        for title, amount, cat, cc, vendor, status in sample_requests:
            pr = PurchaseRequest(
                title=title, description=f"Request for {title.lower()}",
                vendor=vendor, amount=Decimal(str(amount)),
                category=cat, cost_center=cc, status=status,
                requester_id=requester.id, org_id=org.id,
            )
            if status != RequestStatus.DRAFT:
                pr.submitted_at = now - timedelta(days=5)
            if status == RequestStatus.APPROVED:
                pr.approved_at = now - timedelta(days=2)
            if status == RequestStatus.REJECTED:
                pr.rejected_at = now - timedelta(days=1)
            session.add(pr)
            await session.flush()

            # Create audit logs
            audit = AuditLog(
                entity_type="PurchaseRequest", entity_id=pr.id,
                action="created", new_value="draft",
                performed_by=requester.id, org_id=org.id,
            )
            session.add(audit)

            if status != RequestStatus.DRAFT:
                audit2 = AuditLog(
                    entity_type="PurchaseRequest", entity_id=pr.id,
                    action="status_change", old_value="draft", new_value="submitted",
                    performed_by=requester.id, org_id=org.id,
                )
                session.add(audit2)

            if status in (RequestStatus.PENDING_APPROVAL, RequestStatus.APPROVED, RequestStatus.REJECTED):
                audit3 = AuditLog(
                    entity_type="PurchaseRequest", entity_id=pr.id,
                    action="status_change", old_value="submitted", new_value="pending_approval",
                    performed_by=requester.id, org_id=org.id,
                )
                session.add(audit3)

                # Create approval steps
                target_approver = approver2 if amount >= 10000 else approver
                step = ApprovalStep(
                    purchase_request_id=pr.id, policy_id=policy_low.id if amount < 10000 else policy_high.id,
                    approver_id=target_approver.id, step_order=1, status="pending",
                )
                session.add(step)
                await session.flush()

                if status == RequestStatus.APPROVED:
                    step.status = "approved"
                    decision = ApprovalDecision(
                        step_id=step.id, decision=DecisionType.APPROVED,
                        comments="Looks good, approved.", decided_by=target_approver.id,
                    )
                    session.add(decision)
                    audit4 = AuditLog(
                        entity_type="PurchaseRequest", entity_id=pr.id,
                        action="status_change", old_value="pending_approval", new_value="approved",
                        performed_by=target_approver.id, org_id=org.id,
                    )
                    session.add(audit4)

                elif status == RequestStatus.REJECTED:
                    step.status = "rejected"
                    decision = ApprovalDecision(
                        step_id=step.id, decision=DecisionType.REJECTED,
                        comments="Budget constraints, please revise.", decided_by=target_approver.id,
                    )
                    session.add(decision)
                    audit4 = AuditLog(
                        entity_type="PurchaseRequest", entity_id=pr.id,
                        action="status_change", old_value="pending_approval", new_value="rejected",
                        performed_by=target_approver.id, org_id=org.id,
                    )
                    session.add(audit4)

        await session.commit()
        print("Database seeded successfully!")
        print("\nTest accounts:")
        print("  admin@acme.com / admin123 (Admin)")
        print("  approver@acme.com / approver123 (Approver)")
        print("  approver2@acme.com / approver123 (Approver)")
        print("  requester@acme.com / requester123 (Requester)")


if __name__ == "__main__":
    asyncio.run(seed())
