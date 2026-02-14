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

echo "3. Running database seed..."
cd backend
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
echo "  Terminal 1 (backend):  cd backend && uvicorn app.main:app --reload --port 8000"
echo "  Terminal 2 (frontend): cd frontend && npm run dev"
echo ""
echo "Then open http://localhost:3000"
echo ""
echo "Demo accounts:"
echo "  admin@acme.com / admin123"
echo "  approver@acme.com / approver123"
echo "  requester@acme.com / requester123"
