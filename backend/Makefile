.PHONY: help install install-dev clean format lint type-check test test-cov run docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  install       - Install production dependencies"
	@echo "  install-dev   - Install development dependencies"
	@echo "  clean         - Remove build artifacts and cache files"
	@echo "  format        - Format code with black and isort"
	@echo "  lint          - Run flake8 linter"
	@echo "  type-check    - Run mypy type checker"
	@echo "  test          - Run tests with pytest"
	@echo "  test-cov      - Run tests with coverage report"
	@echo "  run           - Run the application locally"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .coverage htmlcov/ dist/ build/

format:
	black src/
	isort src/

lint:
	flake8 src/

type-check:
	mypy src/

test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t genai-knowledge-retrieval:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env genai-knowledge-retrieval:latest
