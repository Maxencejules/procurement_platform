# Procurement Platform

A full-stack procurement intake and approvals application with request management, configurable approval workflows, audit trail, and reporting dashboard.

## Architecture

```
procurement_platform/
├── backend/          Python + FastAPI + Strawberry GraphQL + SQLAlchemy
├── frontend/         React + TypeScript + Apollo Client + Recharts
├── e2e/              Playwright end-to-end tests
├── docker-compose.yml
└── .github/workflows/ci.yml
```

**Backend stack:** FastAPI, Strawberry GraphQL, SQLAlchemy (async), PostgreSQL, JWT auth, Alembic migrations

**Frontend stack:** React 18, TypeScript, Apollo Client, React Router, Recharts

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 20+

### One-command setup

```bash
bash setup.sh
```

Then start the services:

```bash
# Terminal 1 - Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend && npm run dev
```

Open **http://localhost:3000**

### Docker-only setup

```bash
docker compose up --build
```

Open **http://localhost:3000**

### Demo Accounts

| Email | Password | Role |
|-------|----------|------|
| admin@acme.com | admin123 | Admin |
| approver@acme.com | approver123 | Approver |
| approver2@acme.com | approver123 | Approver (VP) |
| requester@acme.com | requester123 | Requester |

## Features

### Request Management
- Create, edit, and submit purchase requests
- Track requests through their lifecycle (Draft → Submitted → Pending Approval → Approved/Rejected)
- Filter and search requests by status, category

### Approval Workflow
- Rules-based approval routing with configurable policies
- Amount thresholds, category-based routing
- Multi-step approval chains
- Approver inbox with approve/reject actions and comments
- Auto-approve when no policies match

### Audit Trail
- Complete audit log for all state changes
- Per-request audit timeline
- Tracks who did what and when

### Reporting Dashboard
- Cycle time per status step
- Requests by category (pie chart)
- Spend breakdown by category
- Approval bottleneck view (pending items per approver)

### Admin
- Create, edit, and delete approval policies
- Configure rules (amount thresholds, category matching)
- Assign approvers and set priority

### Security
- JWT-based authentication
- Role-based access control (RBAC)
- Multi-tenant organization separation
- Protected API endpoints

## Data Model

```
Organization
├── User (role: admin | approver | requester)
├── ApprovalPolicy
│   └── PolicyRule (field, operator, value)
└── PurchaseRequest
    ├── ApprovalStep
    │   └── ApprovalDecision
    └── AuditLog
```

## GraphQL API

The API is available at `/graphql` with an interactive playground.

### Key Queries
- `purchaseRequests` - Paginated list with filters
- `purchaseRequest(id)` - Single request with approval steps
- `approvalInbox` - Pending approvals for current user
- `approvalPolicies` - All org policies
- `auditLogs` - Paginated audit trail
- `cycleTimeReport`, `categoryReport`, `bottleneckReport` - Analytics

### Key Mutations
- `login` - Authenticate and get JWT token
- `createPurchaseRequest` / `updatePurchaseRequest` - CRUD
- `submitRequest` - Submit for approval (triggers routing)
- `approveStep` / `rejectStep` - Approve or reject
- `createApprovalPolicy` / `updateApprovalPolicy` - Admin policy management

## Testing

### Backend unit tests
```bash
cd backend && python -m pytest tests/ -v
```

### Frontend component tests
```bash
cd frontend && npm test
```

### End-to-end tests
```bash
cd e2e && npm install && npx playwright install chromium
npx playwright test
```

The E2E test covers the full flow: login → create request → submit → approve → verify status and audit log.

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs:
1. Backend tests (pytest)
2. Frontend build and tests (vitest)
3. End-to-end tests (Playwright) against a live Postgres instance

## Screens

1. **Login** - Authentication with demo credentials
2. **Request List** - Filterable table of all purchase requests
3. **Create Request** - Form to create and optionally submit a new request
4. **Request Detail** - Full details, approval timeline, and audit trail
5. **Approver Inbox** - Pending approvals with approve/reject actions
6. **Policy Editor** - Admin-only CRUD for approval policies with rule builder
7. **Reports** - Dashboard with cycle time, category breakdown, and bottleneck analysis
