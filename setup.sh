#!/bin/bash
set -e

echo "=== Procurement Platform Setup ==="
echo ""

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required. Install it first."; exit 1; }
command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required."; exit 1; }

echo "1. Starting PostgreSQL..."
docker compose up -d db
echo "   Waiting for Postgres to be ready..."
sleep 5

echo "2. Installing backend dependencies..."
cd backend
pip install -r requirements.txt
cd ..

echo "3. Migrating and seeding the database..."
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://procurement:procurement@localhost:5433/procurement}"
export DATABASE_URL_SYNC="${DATABASE_URL_SYNC:-postgresql://procurement:procurement@localhost:5433/procurement}"
cd backend
python -m alembic upgrade head
python -m app.seed
cd ..

echo "4. Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the app:"
echo "  Set DATABASE_URL and DATABASE_URL_SYNC to the same database (local Docker uses port 5433)."
echo "  Terminal 1 (backend):  cd backend && uvicorn app.main:app --reload --port 8000"
echo "  Terminal 2 (frontend): cd frontend && npm run dev"
echo ""
echo "Then open http://localhost:3000"
echo ""
echo "Demo accounts:"
echo "  admin@acme.com / admin123"
echo "  approver@acme.com / approver123"
echo "  requester@acme.com / requester123"
