.PHONY: install data pipeline test all clean

install:
	pip install -r requirements.txt

data:
	python -m src.generate_source_data

pipeline:
	python -m src.run_pipeline --config config/pipeline.yaml

test:
	pytest tests/ -v

all: data pipeline test

clean:
	rm -rf data/raw data/quarantine data/reports warehouse
