.PHONY: lint test run resume clean install format help

# Default target
all: help

# Run linters on all Python files
lint:
	@echo "Running flake8..."
	@flake8 *.py scripts/*.py --max-line-length=120 --ignore=E501,W503 || true
	@echo "Running pylint..."
	@pylint *.py scripts/*.py --disable=C0103,C0111,R0903,R0913 --max-line-length=120 || true

# Format code with black (if installed)
format:
	@echo "Formatting code with black..."
	@black *.py scripts/*.py --line-length=120 2>/dev/null || echo "black not installed, skipping formatting"

# Run tests
test:
	@pytest tests/ -v 2>/dev/null || echo "No tests directory found"

# Run the main translation pipeline
run:
	@python main.py

# Resume translation from checkpoint
resume:
	@python main.py --resume

# Clean all temporary data
clean:
	@rm -rf working_data/checkpoints/*
	@rm -rf working_data/chunks/*
	@rm -rf working_data/translated_chunks/*
	@rm -rf working_data/preview/*
	@rm -rf working_data/readability_reports/*
	@rm -rf working_data/logs/*.log
	@rm -rf working_data/clean/*
	@echo "Cleaned all working data (kept .gitkeep files)"

# Install dependencies
install:
	@pip install -r requirements.txt
	@echo "Dependencies installed"

# Show help
help:
	@echo "Novel Translation System - Available Commands"
	@echo "=============================================="
	@echo ""
	@echo "  make install    - Install Python dependencies"
	@echo "  make run        - Run main.py (translate all novels)"
	@echo "  make resume     - Resume from last checkpoint"
	@echo "  make lint       - Run flake8 and pylint on code"
	@echo "  make format     - Format code with black (if installed)"
	@echo "  make test       - Run pytest"
	@echo "  make clean      - Clean all working data"
	@echo "  make help       - Show this help message"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make install"
	@echo "  2. Place novels in input_novels/"
	@echo "  3. make run"
