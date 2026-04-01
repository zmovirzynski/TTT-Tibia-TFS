.PHONY: convert lint fix analyze doctor docs test benchmark help

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
	python -m pytest tests/test_ttt.py tests/test_migrator.py tests/test_review.py tests/test_benchmark.py -v

# Run benchmark against example corpus
benchmark:
	python run.py benchmark -i examples/tfs03_input -f tfs03 -t revscript --golden examples/tfs1x_output

help:
	@python run.py --help
