#!/bin/bash
# Start development environment

echo "Starting development environment..."

# Start Docker services (PostgreSQL and Redis)
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 5

echo "Development environment ready!"
echo ""
echo "To start the backend:"
echo "  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "To start the frontend:"
echo "  cd frontend && npm run dev"
echo ""
echo "Or use docker-compose to start all services:"
echo "  docker-compose up"
