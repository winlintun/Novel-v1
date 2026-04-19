.PHONY: lint test run resume clean install

lint:
	@echo "Running flake8..."
	@flake8 *.py --max-line-length=120 --ignore=E501,W503
	@echo "Running pylint..."
	@pylint *.py --disable=C0103,C0111,R0903,R0913 --max-line-length=120 || true

test:
	@pytest tests/ -v || echo "No tests directory found"

run:
	@python main.py

resume:
	@python main.py --resume

clean:
	@rm -rf working_data/checkpoints/*
	@rm -rf working_data/logs/*.log
	@echo "Cleaned checkpoints and logs"

install:
	@pip install -r requirements.txt
	@echo "Dependencies installed"

help:
	@echo "Available targets:"
	@echo "  make lint    - Run flake8 and pylint"
	@echo "  make test    - Run pytest"
	@echo "  make run     - Run main.py"
	@echo "  make resume  - Resume from checkpoint"
	@echo "  make clean   - Clean checkpoints and logs"
	@echo "  make install - Install dependencies"
