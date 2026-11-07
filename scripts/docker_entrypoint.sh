#!/usr/bin/env bash
# ============================================================
# AegisOps container entrypoint (dispatches by MODE)
#   MODE=api → bootstrap + uvicorn
#   MODE=ui  → wait for API + streamlit
# ============================================================
set -euo pipefail

MODE="${1:-api}"
echo "===================================================================="
echo "[entrypoint] AegisOps starting in MODE=${MODE}"
echo "===================================================================="

case "$MODE" in
  api)
    echo "[entrypoint] Running one-shot bootstrap (idempotent)..."
    python scripts/docker_bootstrap.py || {
      echo "[entrypoint] WARNING: bootstrap failed, continuing anyway"
    }
    echo "[entrypoint] Starting Uvicorn..."
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port 8000 \
      --log-level info \
      --proxy-headers \
      --forwarded-allow-ips '*'
    ;;

  ui)
    echo "[entrypoint] Waiting for API at http://api:8000/health ..."
    for i in $(seq 1 90); do
      if curl -sf http://api:8000/health >/dev/null 2>&1; then
        echo "[entrypoint] API is ready after ${i} attempt(s)"
        break
      fi
      sleep 2
    done

    echo "[entrypoint] Starting Streamlit..."
    exec streamlit run admin/app.py \
      --server.port 8501 \
      --server.address 0.0.0.0 \
      --server.headless true \
      --browser.gatherUsageStats false
    ;;

  *)
    echo "[entrypoint] Unknown MODE='${MODE}', exec'ing directly"
    exec "$@"
    ;;
esac