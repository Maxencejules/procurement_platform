import pytest
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import PurchaseRequest, RequestStatus, ApprovalPolicy, PolicyRule
from app.models.approval import ApprovalStep, DecisionType
from app.workflow.engine import (
    evaluate_rule, matches_policy, route_approval, process_decision, transition_status,
)


class TestEvaluateRule:
    def test_amount_gt(self, sample_request):
        rule = PolicyRule(field="amount", operator="gt", value="1000")
        assert evaluate_rule(rule, sample_request) is True  # 5000 > 1000

    def test_amount_lt(self, sample_request):
        rule = PolicyRule(field="amount", operator="lt", value="1000")
        assert evaluate_rule(rule, sample_request) is False  # 5000 is not < 1000

    def test_amount_gte(self, sample_request):
        rule = PolicyRule(field="amount", operator="gte", value="5000")
        assert evaluate_rule(rule, sample_request) is True  # 5000 >= 5000

    def test_category_eq(self, sample_request):
        rule = PolicyRule(field="category", operator="eq", value="IT")
        assert evaluate_rule(rule, sample_request) is True

    def test_category_eq_case_insensitive(self, sample_request):
        rule = PolicyRule(field="category", operator="eq", value="it")
        assert evaluate_rule(rule, sample_request) is True

    def test_category_in(self, sample_request):
        rule = PolicyRule(field="category", operator="in", value="IT, Marketing")
        assert evaluate_rule(rule, sample_request) is True

    def test_category_not_in(self, sample_request):
        rule = PolicyRule(field="category", operator="in", value="Marketing, HR")
        assert evaluate_rule(rule, sample_request) is False

    def test_unknown_field_returns_false(self, sample_request):
        rule = PolicyRule(field="nonexistent", operator="eq", value="x")
        assert evaluate_rule(rule, sample_request) is False


class TestMatchesPolicy:
    async def test_policy_with_matching_rules(self, session, approval_policy, sample_request):
        # Eagerly reload policy with rules for aiosqlite compatibility
        result = await session.execute(
            select(ApprovalPolicy).options(selectinload(ApprovalPolicy.rules))
            .where(ApprovalPolicy.id == approval_policy.id)
        )
        policy = result.scalar_one()
        assert matches_policy(policy, sample_request) is True

    async def test_policy_without_rules_matches_all(self, session, org, approver_user, sample_request):
        policy = ApprovalPolicy(
            name="Match All", org_id=org.id, approver_id=approver_user.id, priority=1,
        )
        session.add(policy)
        await session.flush()
        # Reload to get empty rules collection
        result = await session.execute(
            select(ApprovalPolicy).options(selectinload(ApprovalPolicy.rules))
            .where(ApprovalPolicy.id == policy.id)
        )
        policy = result.scalar_one()
        assert matches_policy(policy, sample_request) is True


class TestTransitionStatus:
    @pytest.mark.asyncio
    async def test_valid_transition(self, session, sample_request, requester_user):
        await transition_status(session, sample_request, RequestStatus.SUBMITTED, requester_user.id)
        assert sample_request.status == RequestStatus.SUBMITTED
        assert sample_request.submitted_at is not None

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, session, sample_request, requester_user):
        with pytest.raises(ValueError, match="Invalid transition"):
            await transition_status(session, sample_request, RequestStatus.APPROVED, requester_user.id)


class TestRouteApproval:
    @pytest.mark.asyncio
    async def test_route_creates_steps(self, session, sample_request, approval_policy, requester_user):
        # First transition to submitted
        await transition_status(session, sample_request, RequestStatus.SUBMITTED, requester_user.id)

        steps = await route_approval(session, sample_request, requester_user.id)
        assert len(steps) == 1
        assert steps[0].approver_id == approval_policy.approver_id
        assert sample_request.status == RequestStatus.PENDING_APPROVAL


class TestProcessDecision:
    @pytest.mark.asyncio
    async def test_approve_single_step(self, session, sample_request, approval_policy, requester_user, approver_user):
        await transition_status(session, sample_request, RequestStatus.SUBMITTED, requester_user.id)
        steps = await route_approval(session, sample_request, requester_user.id)

        await process_decision(session, steps[0], DecisionType.APPROVED, approver_user.id, "Looks good")
        assert sample_request.status == RequestStatus.APPROVED
        assert steps[0].status == "approved"

    @pytest.mark.asyncio
    async def test_reject_single_step(self, session, sample_request, approval_policy, requester_user, approver_user):
        await transition_status(session, sample_request, RequestStatus.SUBMITTED, requester_user.id)
        steps = await route_approval(session, sample_request, requester_user.id)

        await process_decision(session, steps[0], DecisionType.REJECTED, approver_user.id, "Not now")
        assert sample_request.status == RequestStatus.REJECTED
        assert steps[0].status == "rejected"
