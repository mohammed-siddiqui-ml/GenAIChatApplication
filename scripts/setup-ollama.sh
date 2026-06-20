#!/bin/bash

# Ollama Setup Script
# This script downloads the required models for Ollama

set -e

echo "=================================="
echo "Ollama Model Setup Script"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Ollama container is running
if ! docker ps | grep -q knowledge_ollama; then
    echo -e "${RED}Error: Ollama container is not running${NC}"
    echo "Please start the services first with: docker-compose up -d"
    exit 1
fi

echo -e "${GREEN}✓ Ollama container is running${NC}"
echo ""

# Function to pull a model
pull_model() {
    local model=$1
    echo -e "${YELLOW}Downloading $model...${NC}"
    docker exec -it knowledge_ollama ollama pull "$model"
    echo -e "${GREEN}✓ $model downloaded successfully${NC}"
    echo ""
}

# Function to check if model exists
model_exists() {
    local model=$1
    docker exec knowledge_ollama ollama list | grep -q "$model"
}

echo "This script will download the following models:"
echo "  1. llama2 (~4GB) - Chat model"
echo "  2. nomic-embed-text (~274MB) - Embedding model"
echo ""
echo "Total download size: ~4.3GB"
echo ""

read -p "Do you want to continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 0
fi

echo ""
echo "Starting model downloads..."
echo ""

# Download chat model
if model_exists "llama2"; then
    echo -e "${YELLOW}llama2 is already installed${NC}"
    echo ""
else
    pull_model "llama2"
fi

# Download embedding model
if model_exists "nomic-embed-text"; then
    echo -e "${YELLOW}nomic-embed-text is already installed${NC}"
    echo ""
else
    pull_model "nomic-embed-text"
fi

echo ""
echo -e "${GREEN}=================================="
echo "Setup Complete!"
echo "==================================${NC}"
echo ""
echo "Installed models:"
docker exec knowledge_ollama ollama list
echo ""
echo "You can now use the application with Ollama!"
echo ""
echo "To test the models:"
echo "  docker exec -it knowledge_ollama ollama run llama2 'Hello!'"
echo ""
echo "To download additional models:"
echo "  docker exec -it knowledge_ollama ollama pull <model-name>"
echo ""
echo "Available models: https://ollama.com/library"
echo ""
