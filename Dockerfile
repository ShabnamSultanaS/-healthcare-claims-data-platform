FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Generate source data and run the full pipeline
CMD ["sh", "-c", "python -m src.generate_source_data && python -m src.run_pipeline"]
