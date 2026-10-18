#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# OS-level environment layer (APP_* prefix)
export APP_PORT=8188
export APP_WORKERS=2
export APP_DEBUG=true
export APP_LOG_LEVEL=error
export APP_API_KEY=key-lt45g8x3px

# Which config.<env>.yaml to load
export CONFIG_ENV="${CONFIG_ENV:-development}"

# The port uvicorn listens on (separate from the "port" config value)
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
