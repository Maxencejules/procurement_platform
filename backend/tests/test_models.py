import pytest
from decimal import Decimal

from app.models import (
    Organization, User, Role, PurchaseRequest, RequestStatus,
    ApprovalPolicy, PolicyRule,
)
from app.models.purchase_request import VALID_TRANSITIONS


class TestPurchaseRequest:
    def test_valid_transitions_from_draft(self):
        allowed = VALID_TRANSITIONS[RequestStatus.DRAFT]
        assert RequestStatus.SUBMITTED in allowed
        assert RequestStatus.CANCELLED in allowed
        assert RequestStatus.APPROVED not in allowed

    def test_valid_transitions_from_submitted(self):
        allowed = VALID_TRANSITIONS[RequestStatus.SUBMITTED]
        assert RequestStatus.PENDING_APPROVAL in allowed
        assert RequestStatus.CANCELLED in allowed

    def test_valid_transitions_from_pending(self):
        allowed = VALID_TRANSITIONS[RequestStatus.PENDING_APPROVAL]
        assert RequestStatus.APPROVED in allowed
        assert RequestStatus.REJECTED in allowed
        assert RequestStatus.CANCELLED in allowed

    def test_terminal_states_have_no_transitions(self):
        assert len(VALID_TRANSITIONS[RequestStatus.APPROVED]) == 0
        assert len(VALID_TRANSITIONS[RequestStatus.REJECTED]) == 0
        assert len(VALID_TRANSITIONS[RequestStatus.CANCELLED]) == 0

    @pytest.mark.asyncio
    async def test_create_request(self, session, org, requester_user):
        pr = PurchaseRequest(
            title="Test",
            vendor="Vendor",
            amount=Decimal("100.00"),
            category="IT",
            cost_center="ENG-001",
            status=RequestStatus.DRAFT,
            requester_id=requester_user.id,
            org_id=org.id,
        )
        session.add(pr)
        await session.flush()
        assert pr.id is not None
        assert pr.status == RequestStatus.DRAFT


class TestUser:
    @pytest.mark.asyncio
    async def test_create_user(self, session, org):
        user = User(
            email="new@test.com",
            password_hash="hashed",
            full_name="New User",
            role=Role.REQUESTER,
            org_id=org.id,
        )
        session.add(user)
        await session.flush()
        assert user.id is not None
        assert user.role == Role.REQUESTER
