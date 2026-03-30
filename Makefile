.PHONY: convert lint fix analyze doctor docs test help

# Run script conversion using settings from config.toml
convert:
	python run.py convert

# Static analysis — usage: make lint p=./data/scripts
lint:
	python run.py lint $(p)

# Auto-fix issues — usage: make fix p=./data/scripts
fix:
	python run.py fix $(p)

# Full server analysis — usage: make analyze p=./data
analyze:
	python run.py analyze $(p)

# Health check — usage: make doctor p=./data
doctor:
	python run.py doctor $(p)

# Generate documentation — usage: make docs p=./data
docs:
	python run.py docs $(p)

# Run tests
test:
	python -m pytest tests/test_ttt.py -v

help:
	@python run.py --help
