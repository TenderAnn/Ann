FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    MODEL_PACK=models/intent_baseline.joblib \
    ONTOLOGY=data/ontology_insurance_zh.yaml \
    SYNONYMS=data/synonyms_insurance_zh_v1.1.tsv \
    TEMPLATES=data/templates_canonical_zh.json \
    THRESHOLD_JSON=configs/intent_threshold.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD curl -fsS http://localhost:${PORT}/docs || exit 1

CMD ["uvicorn", "api.serve_intent:app", "--host", "0.0.0.0", "--port", "8080"]
