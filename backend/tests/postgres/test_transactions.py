"""Real PostgreSQL API/transaction proof; SQLite cannot verify these locks."""
import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import select, func, text, delete
from sqlalchemy.exc import IntegrityError

from app.auth.jwt import create_access_token
from app.auth.rbac import AuthContext
from app.database import Base
from app.errors import WorkflowError
from app.main import app, get_db_session, schema
from app.models import Organization, User, Role, PurchaseRequest, RequestStatus, AuditLog
from app.models.approval import ApprovalPolicy, ApprovalStep, ApprovalDecision, DecisionType, PolicyRule
from app.schema import mutations
from app.workflow.engine import process_decision
from tests.postgres.conftest import migrate

pytestmark = pytest.mark.postgres

SUBMIT = "mutation($id: ID!) { submitRequest(id: $id) { id status approvalSteps { id } } }"
APPROVE = "mutation($id: ID!) { approveStep(stepId: $id) { id status decision { id } } }"
CANCEL = "mutation($id: ID!) { cancelRequest(id: $id) { id status } }"
CREATE = """mutation($amount: Float!) {
    createPurchaseRequest(input: {title: "New", vendor: "Vendor", amount: $amount,
        category: "IT", costCenter: "CC"}) { id amount status }
}"""


@pytest_asyncio.fixture
async def data(pg_sessions):
    async with pg_sessions() as session:
        org = Organization(name="Proof", slug="proof")
        foreign_org = Organization(name="Foreign", slug="foreign")
        session.add_all([org, foreign_org])
        await session.flush()
        users = {}
        for name, role, tenant in [
            ("requester", Role.REQUESTER, org), ("other", Role.REQUESTER, org),
            ("admin", Role.ADMIN, org), ("approver", Role.APPROVER, org),
            ("foreign", Role.APPROVER, foreign_org),
        ]:
            user = User(email=f"{name}@proof.test", password_hash="unused",
                        full_name=name, role=role, org_id=tenant.id)
            users[name] = user
            session.add(user)
        await session.flush()
        request = PurchaseRequest(title="Proof", vendor="Vendor", amount=Decimal("100.00"),
                                  category="IT", cost_center="CC", requester_id=users["requester"].id,
                                  org_id=org.id)
        policies = [ApprovalPolicy(name=f"Policy {i}", org_id=org.id,
                                   approver_id=users["approver"].id, priority=i) for i in [1, 2]]
        session.add_all([request, *policies])
        await session.commit()
        return SimpleNamespace(
            request=request.id, org=org.id,
            users={name: (user.id, user.org_id, user.role.value) for name, user in users.items()},
        )


def auth(data, name):
    user, org, role = data.users[name]
    return AuthContext(user_id=str(user), org_id=str(org), role=role)


async def execute(session, data, query, variables=None, name="requester"):
    return await schema.execute(query, variable_values=variables,
                                context_value={"session": session, "auth": auth(data, name)})


def error_code(result):
    assert result.errors, result.data
    return result.errors[0].extensions["code"]


async def submit(pg_sessions, data):
    async with pg_sessions() as session:
        result = await execute(session, data, SUBMIT, {"id": str(data.request)})
        assert not result.errors
        return [item["id"] for item in result.data["submitRequest"]["approvalSteps"]]


async def wait_for_lock(engine, pid, task):
    # Observe the actual server wait, rather than relying on a timed sleep race.
    async with engine.connect() as observer:
        for _ in range(500):
            await observer.execute(text("SELECT pg_stat_clear_snapshot()"))
            state = await observer.scalar(text(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"
            ), {"pid": pid})
            if state == "Lock":
                assert not task.done()
                return
            if task.done():
                pytest.fail("Competing mutation completed without waiting for the request lock")
            await asyncio.sleep(0.01)
    pytest.fail("PostgreSQL did not report the expected row-lock wait")


@pytest.mark.parametrize("same_step", [True, False], ids=["duplicate-decision", "sibling-final-approval"])
async def test_decisions_wait_and_reload_cached_state(pg_engine, pg_sessions, data, same_step):
    step_ids = await submit(pg_sessions, data)
    async with pg_sessions() as first, pg_sessions() as second:
        locked = (await first.execute(select(PurchaseRequest).where(
            PurchaseRequest.id == data.request).with_for_update(of=PurchaseRequest))).scalar_one()
        cached = await second.get(PurchaseRequest, data.request)
        assert cached.status == locked.status == RequestStatus.PENDING_APPROVAL
        pid = await second.scalar(text("SELECT pg_backend_pid()"))
        competing = asyncio.create_task(execute(second, data, APPROVE,
            {"id": step_ids[0 if same_step else 1]}, "approver"))
        try:
            await wait_for_lock(pg_engine, pid, competing)
            step = locked.approval_steps[0]
            await process_decision(first, step, DecisionType.APPROVED, data.users["approver"][0])
            await first.commit()
            result = await asyncio.wait_for(competing, 10)
        finally:
            if not competing.done():
                competing.cancel()
                await asyncio.gather(competing, return_exceptions=True)
        if same_step:
            assert error_code(result) == "CONFLICT"
        else:
            assert not result.errors
    async with pg_sessions() as verify:
        request = await verify.get(PurchaseRequest, data.request)
        assert request.status == (RequestStatus.PENDING_APPROVAL if same_step else RequestStatus.APPROVED)
        assert await verify.scalar(select(func.count()).select_from(ApprovalDecision)) == (1 if same_step else 2)
        final_audits = await verify.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_id == data.request, AuditLog.new_value == "approved"))
        assert final_audits == (0 if same_step else 1)


async def test_cancel_wins_while_approval_waits(pg_engine, pg_sessions, data):
    step_ids = await submit(pg_sessions, data)
    async with pg_sessions() as owner, pg_sessions() as decider:
        await owner.execute(select(PurchaseRequest).where(PurchaseRequest.id == data.request)
                            .with_for_update(of=PurchaseRequest))
        cached = await decider.get(PurchaseRequest, data.request)
        assert cached.status == RequestStatus.PENDING_APPROVAL
        pid = await decider.scalar(text("SELECT pg_backend_pid()"))
        competing = asyncio.create_task(execute(decider, data, APPROVE, {"id": step_ids[0]}, "approver"))
        try:
            await wait_for_lock(pg_engine, pid, competing)
            result = await execute(owner, data, CANCEL, {"id": str(data.request)})
            assert not result.errors
            assert error_code(await asyncio.wait_for(competing, 10)) == "CONFLICT"
        finally:
            if not competing.done():
                competing.cancel()
                await asyncio.gather(competing, return_exceptions=True)
    async with pg_sessions() as verify:
        request = await verify.get(PurchaseRequest, data.request)
        assert request.status == RequestStatus.CANCELLED
        assert all(step.status == "skipped" for step in request.approval_steps)
        assert await verify.scalar(select(func.count()).select_from(ApprovalDecision)) == 0


async def test_concurrent_submit_creates_one_chain(pg_engine, pg_sessions, data):
    async with pg_sessions() as first, pg_sessions() as second:
        await first.execute(select(PurchaseRequest).where(PurchaseRequest.id == data.request)
                            .with_for_update(of=PurchaseRequest))
        cached = await second.get(PurchaseRequest, data.request)
        assert cached.status == RequestStatus.DRAFT
        pid = await second.scalar(text("SELECT pg_backend_pid()"))
        competing = asyncio.create_task(execute(second, data, SUBMIT, {"id": str(data.request)}))
        try:
            await wait_for_lock(pg_engine, pid, competing)
            assert not (await execute(first, data, SUBMIT, {"id": str(data.request)})).errors
            assert error_code(await asyncio.wait_for(competing, 10)) == "CONFLICT"
        finally:
            if not competing.done():
                competing.cancel()
                await asyncio.gather(competing, return_exceptions=True)
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(ApprovalStep)) == 2
        assert await verify.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_id == data.request, AuditLog.new_value == "submitted")) == 1


async def test_failure_after_writes_rolls_back_and_session_recovers(pg_sessions, data, monkeypatch):
    original = mutations.route_approval

    async def fail_after_route(*args):
        await original(*args)
        await args[0].flush()  # State, steps and audit SQL have all reached PostgreSQL.
        raise WorkflowError("Forced routing failure")

    monkeypatch.setattr(mutations, "route_approval", fail_after_route)
    async with pg_sessions() as session:
        assert error_code(await execute(session, data, SUBMIT, {"id": str(data.request)})) == "CONFLICT"
        async with pg_sessions() as verify:
            assert (await verify.get(PurchaseRequest, data.request)).status == RequestStatus.DRAFT
            assert await verify.scalar(select(func.count()).select_from(ApprovalStep)) == 0
            assert await verify.scalar(select(func.count()).select_from(AuditLog)) == 0
        monkeypatch.setattr(mutations, "route_approval", original)
        assert not (await execute(session, data, SUBMIT, {"id": str(data.request)})).errors


async def test_auto_approve_no_policy(pg_sessions, data):
    async with pg_sessions() as session:
        await session.execute(delete(ApprovalPolicy))
        await session.commit()
        result = await execute(session, data, SUBMIT, {"id": str(data.request)})
        assert not result.errors
        assert result.data["submitRequest"]["status"] == "approved"
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(ApprovalStep)) == 0
        assert await verify.scalar(select(func.count()).select_from(AuditLog)) == 2


@pytest.mark.parametrize("amount", [-1, 0, 1.001, 10000000000])
async def test_invalid_money_writes_nothing(pg_sessions, data, amount):
    async with pg_sessions() as session:
        assert error_code(await execute(session, data, CREATE, {"amount": amount})) == "BAD_USER_INPUT"
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(PurchaseRequest)) == 1
        assert await verify.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.parametrize("query", [CANCEL, SUBMIT,
    'mutation($id: ID!) { updatePurchaseRequest(id: $id, input: {title: "Stolen"}) { id } }'])
async def test_request_owner_or_admin(pg_sessions, data, query):
    async with pg_sessions() as session:
        assert error_code(await execute(session, data, query, {"id": str(data.request)}, "other")) == "FORBIDDEN"
        assert not (await execute(session, data, query, {"id": str(data.request)}, "admin")).errors


async def test_foreign_approver_and_invalid_rule_leave_no_policy(pg_sessions, data):
    query = """mutation($approver: ID!, $field: String!, $value: String!) {
        createApprovalPolicy(input: {name: "Invalid", approverId: $approver,
            rules: [{field: $field, operator: "gte", value: $value}]}) { id }
    }"""
    async with pg_sessions() as session:
        for name, field, value in [("foreign", "amount", "1"), ("approver", "unknown", "1"),
                                   ("approver", "amount", "NaN"), ("approver", "amount", "Infinity")]:
            result = await execute(session, data, query,
                                   {"approver": str(data.users[name][0]), "field": field, "value": value}, "admin")
            assert error_code(result) == "BAD_USER_INPUT"
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(ApprovalPolicy)) == 2


async def test_policy_create_and_replace_rules(pg_sessions, data):
    async with pg_sessions() as session:
        created = await execute(session, data, """mutation($id: ID!) {
            createApprovalPolicy(input: {name: "New policy", approverId: $id,
                rules: [{field: "amount", operator: "gte", value: "100"}]}) {
                id rules { id field value }
            }
        }""", {"id": str(data.users["approver"][0])}, "admin")
        assert not created.errors
        policy = created.data["createApprovalPolicy"]
        old_rule = policy["rules"][0]["id"]
        updated = await execute(session, data, """mutation($id: ID!) {
            updateApprovalPolicy(id: $id, input: {
                rules: [{field: "category", operator: "eq", value: "IT"}]}) {
                rules { id field value }
            }
        }""", {"id": policy["id"]}, "admin")
        assert not updated.errors
        rule = updated.data["updateApprovalPolicy"]["rules"]
        assert len(rule) == 1 and rule[0]["field"] == "category" and rule[0]["id"] != old_rule
    async with pg_sessions() as verify:
        assert await verify.get(PolicyRule, UUID(old_rule)) is None


async def test_padded_rule_values_are_stored_and_matched_consistently(pg_sessions, data):
    async with pg_sessions() as session:
        await session.execute(delete(ApprovalPolicy))
        await session.commit()
        query = """mutation($approver: ID!, $value: String!) {
            createApprovalPolicy(input: {name: "Category review", approverId: $approver,
                rules: [{field: "category", operator: "eq", value: $value}]}) {
                id rules { value }
            }
        }"""
        created = await execute(session, data, query,
            {"approver": str(data.users["approver"][0]), "value": " " * 256 + "IT"}, "admin")
        assert not created.errors
        policy = created.data["createApprovalPolicy"]
        assert policy["rules"] == [{"value": "IT"}]
        updated = await execute(session, data, """mutation($id: ID!, $value: String!) {
            updateApprovalPolicy(id: $id, input: {
                rules: [{field: "category", operator: "eq", value: $value}]}) { rules { value } }
        }""", {"id": policy["id"], "value": " IT "}, "admin")
        assert not updated.errors
        assert updated.data["updateApprovalPolicy"]["rules"] == [{"value": "IT"}]
        # Existing padded values from the old writer must also match, rather than
        # silently falling through to the no-policy auto-approval path.
        rule = await session.scalar(select(PolicyRule).where(PolicyRule.policy_id == UUID(policy["id"])))
        rule.value = " IT "
        await session.commit()
        result = await execute(session, data, SUBMIT, {"id": str(data.request)})
        assert not result.errors
        assert result.data["submitRequest"]["status"] == "pending_approval"
        assert len(result.data["submitRequest"]["approvalSteps"]) == 1


async def test_constraint_error_rolls_back_and_maps_to_conflict(pg_sessions, data):
    await submit(pg_sessions, data)
    async with pg_sessions() as session:
        policy_id = await session.scalar(select(ApprovalPolicy.id).order_by(ApprovalPolicy.priority))
        result = await execute(session, data,
            'mutation($id: ID!) { deleteApprovalPolicy(id: $id) }', {"id": str(policy_id)}, "admin")
        assert error_code(result) == "CONFLICT"  # Historical steps reference this policy.
        assert not (await execute(session, data, CREATE, {"amount": 1})).errors
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(ApprovalPolicy)) == 2


async def test_direct_writers_cannot_duplicate_steps_or_decisions(pg_sessions, data):
    step_ids = await submit(pg_sessions, data)
    async with pg_sessions() as session:
        step = (await session.execute(select(ApprovalStep).order_by(ApprovalStep.step_order))).scalars().first()
        session.add(ApprovalStep(purchase_request_id=data.request, policy_id=step.policy_id,
                                 approver_id=step.approver_id, step_order=step.step_order))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
        assert not (await execute(session, data, APPROVE, {"id": step_ids[0]}, "approver")).errors
        session.add(ApprovalDecision(step_id=UUID(step_ids[0]), decision=DecisionType.REJECTED,
                                     decided_by=data.users["approver"][0]))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with pg_sessions() as verify:
        assert await verify.scalar(select(func.count()).select_from(ApprovalStep)) == 2
        assert await verify.scalar(select(func.count()).select_from(ApprovalDecision)) == 1


async def test_http_error_codes_and_success(pg_sessions, data):
    async def db():
        async with pg_sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = db
    user, org, role = data.users["requester"]
    token = create_access_token(user, org, role)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://proof") as client:
            unauth = await client.post("/graphql", json={"query": CREATE, "variables": {"amount": 1}})
            assert unauth.json()["errors"][0]["extensions"]["code"] == "UNAUTHENTICATED"
            client.headers["Authorization"] = f"Bearer {token}"
            invalid = await client.post("/graphql", json={"query": SUBMIT, "variables": {"id": "bad"}})
            assert invalid.json()["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"
            valid = await client.post("/graphql", json={"query": CREATE, "variables": {"amount": 12.34}})
            assert valid.status_code == 200
            assert not valid.json().get("errors")
            assert valid.json()["data"]["createPurchaseRequest"]["amount"] == 12.34
    finally:
        app.dependency_overrides.pop(get_db_session, None)


async def test_migration_round_trip_and_constraints(pg_engine, pg_sessions, data):
    async with pg_engine.connect() as connection:
        def compare(sync):
            return compare_metadata(MigrationContext.configure(sync), Base.metadata)
        assert await connection.run_sync(compare) == []
    # A direct SQL writer must also respect the monetary constraint.
    async with pg_sessions() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("UPDATE purchase_requests SET amount = 'NaN' WHERE id = :id"),
                                  {"id": data.request})
        await session.rollback()
    async with pg_engine.begin() as connection:
        await connection.run_sync(lambda sync: migrate(sync, "base", downgrade=True))
        await connection.run_sync(migrate)
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
