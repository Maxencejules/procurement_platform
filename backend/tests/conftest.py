import asyncio
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.auth.jwt import hash_password
from app.models import (
    Organization, User, Role, PurchaseRequest, RequestStatus,
    ApprovalPolicy, PolicyRule,
)


TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def org(session: AsyncSession):
    org = Organization(name="Test Org", slug="test-org")
    session.add(org)
    await session.flush()
    return org


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession, org: Organization):
    user = User(
        email="admin@test.com",
        password_hash=hash_password("password"),
        full_name="Test Admin",
        role=Role.ADMIN,
        org_id=org.id,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def approver_user(session: AsyncSession, org: Organization):
    user = User(
        email="approver@test.com",
        password_hash=hash_password("password"),
        full_name="Test Approver",
        role=Role.APPROVER,
        org_id=org.id,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def requester_user(session: AsyncSession, org: Organization):
    user = User(
        email="requester@test.com",
        password_hash=hash_password("password"),
        full_name="Test Requester",
        role=Role.REQUESTER,
        org_id=org.id,
    )
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def sample_request(session: AsyncSession, org: Organization, requester_user: User):
    pr = PurchaseRequest(
        title="Test Purchase",
        description="Test description",
        vendor="Test Vendor",
        amount=Decimal("5000.00"),
        category="IT",
        cost_center="ENG-001",
        status=RequestStatus.DRAFT,
        requester_id=requester_user.id,
        org_id=org.id,
    )
    session.add(pr)
    await session.flush()
    return pr


@pytest_asyncio.fixture
async def approval_policy(session: AsyncSession, org: Organization, approver_user: User):
    policy = ApprovalPolicy(
        name="Standard Approval",
        description="Approval for all requests",
        org_id=org.id,
        approver_id=approver_user.id,
        priority=1,
        is_active=True,
    )
    session.add(policy)
    await session.flush()

    rule = PolicyRule(
        policy_id=policy.id,
        field="amount",
        operator="gte",
        value="1000",
    )
    session.add(rule)
    await session.flush()
    return policy
