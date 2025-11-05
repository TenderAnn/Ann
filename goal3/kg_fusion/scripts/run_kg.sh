#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$KG_ROOT/.." && pwd)"

export INTENT_BASE_URL=${INTENT_BASE_URL:-http://127.0.0.1:8080}
export KG_FUSION_PORT=${KG_FUSION_PORT:-8081}
export KG_SQLITE=${KG_SQLITE:-"$KG_ROOT/data/kg/graph.sqlite"}
export RECENCY_CSV=${RECENCY_CSV:-"$KG_ROOT/data/kg/recency_meta.csv"}
export VEC_INDEX=${VEC_INDEX:-"$KG_ROOT/data/index/vec.index"}
export VEC_META=${VEC_META:-"$KG_ROOT/data/index/vec.meta.csv"}
export EMB_MODEL=${EMB_MODEL:-"BAAI/bge-small-zh-v1.5"}
if [[ -z "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="$REPO_ROOT"
else
  export PYTHONPATH="$REPO_ROOT:$PYTHONPATH"
fi
cd "$REPO_ROOT"
uvicorn kg_fusion.app.main:app --host 127.0.0.1 --port "$KG_FUSION_PORT" --reload
