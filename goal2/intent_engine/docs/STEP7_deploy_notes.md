# STEP7 Deploy Notes

## Image build & runtime configuration
- Base image: `python:3.10-slim`
- Working dir: `/app`
- Default env vars (override via `-e KEY=value`):
  - `PORT=8080`, `HOST=0.0.0.0`
  - `MODEL_PACK=models/intent_baseline.joblib`
  - `ONTOLOGY=data/ontology_insurance_zh.yaml`
  - `SYNONYMS=data/synonyms_insurance_zh_v1.1.tsv`
  - `TEMPLATES=data/templates_canonical_zh.json`
  - `THRESHOLD_JSON=configs/intent_threshold.json`

## Build command
```bash
docker build -t intent-engine:1.0.0 .
```

## Run command
```bash
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e MODEL_PACK=models/intent_baseline.joblib \
  intent-engine:1.0.0
```

## Healthcheck
- Container exposes `/docs`; Dockerfile healthcheck hits `http://localhost:${PORT}/docs` every 30s.

> Docker CLI isn’t available in this environment, so the commands above weren’t executed here; run them on your deployment host.
