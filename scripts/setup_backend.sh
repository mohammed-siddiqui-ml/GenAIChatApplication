#!/bin/bash
# Backend setup script

echo "Setting up backend environment..."

cd backend || exit 1

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy .env.example to .env if .env doesn't exist
if [ ! -f ../.env ]; then
    echo "Creating .env file..."
    cp ../.env.example ../.env
    echo "Please update .env file with your configuration"
fi

echo "Backend setup complete!"
echo "To activate the virtual environment, run: source backend/venv/bin/activate"
echo "To start the backend server, run: uvicorn app.main:app --reload"
