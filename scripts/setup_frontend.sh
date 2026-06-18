#!/bin/bash
# Frontend setup script

echo "Setting up frontend environment..."

cd frontend || exit 1

# Install dependencies
echo "Installing npm dependencies..."
npm install

echo "Frontend setup complete!"
echo "To start the frontend development server, run: cd frontend && npm run dev"
