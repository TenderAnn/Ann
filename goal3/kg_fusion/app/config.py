import os

INTENT_BASE_URL = os.getenv("INTENT_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
KG_FUSION_PORT = int(os.getenv("KG_FUSION_PORT", "8081"))
