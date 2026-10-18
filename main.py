"""FastAPI service that merges layered configuration.

Precedence (low -> high):
    defaults -> config.<env>.yaml -> .env -> OS env (APP_*) -> ?set=key=value
"""
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

PREFIX = "APP_"
ALIASES = {"num_workers": "workers"}  # applied in the .env layer
INT_KEYS = {"port", "workers"}
BOOL_KEYS = {"debug"}
SECRET_KEYS = {"api_key"}
TRUE_VALUES = {"true", "1", "yes", "on"}
MASK = "****"

DEFAULTS: Dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="Effective Config Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


def _env_name() -> str:
    # CONFIG_ENV (not APP_*) selects the YAML file, so it never leaks into the config layers.
    name = os.environ.get("CONFIG_ENV", "development")
    return name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else "development"


def load_yaml(env_name: str) -> Dict[str, Any]:
    path = BASE_DIR / f"config.{env_name}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip().lower(): v for k, v in data.items()}


def _normalize_key(raw: str) -> str:
    key = raw.strip()
    if key.upper().startswith(PREFIX):
        key = key[len(PREFIX):]
    return key.lower()


def load_dotenv(path: Path) -> Dict[str, Any]:
    """Minimal .env parser. Does NOT modify os.environ."""
    result: Dict[str, Any] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        raw_key, raw_value = line.split("=", 1)
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        key = _normalize_key(raw_key)
        if not key:
            continue
        key = ALIASES.get(key, key)
        result[key] = value
    return result


def load_os_env() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name, value in os.environ.items():
        if name.startswith(PREFIX) and len(name) > len(PREFIX):
            result[name[len(PREFIX):].lower()] = value
    return result


def coerce(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        if isinstance(value, bool):
            return int(value)
        try:
            return int(str(value).strip())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"'{key}' must be an integer, got {value!r}")
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in TRUE_VALUES
    if value is None:
        return ""
    return str(value)


def merge_layers(overrides: list) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(DEFAULTS)
    merged.update(load_yaml(_env_name()))
    merged.update(load_dotenv(BASE_DIR / ".env"))
    merged.update(load_os_env())

    for item in overrides:
        if "=" not in item:
            raise HTTPException(status_code=400, detail=f"Invalid set parameter {item!r}; expected key=value")
        key, value = item.split("=", 1)
        key = key.strip().lower()
        if not key:
            raise HTTPException(status_code=400, detail=f"Invalid set parameter {item!r}: empty key")
        merged[key] = value
    return merged


@app.get("/effective-config")
def effective_config(request: Request):
    merged = merge_layers(request.query_params.getlist("set"))
    return {k: (MASK if k in SECRET_KEYS else coerce(k, v)) for k, v in merged.items()}


@app.get("/health")
def health():
    return {"status": "ok"}
