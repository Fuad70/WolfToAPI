from __future__ import annotations

import os
from pathlib import Path

APP_PORT = int(os.getenv("APP_PORT", "4040"))
AGENT_WS_PORT = int(os.getenv("AGENT_WS_PORT", "8765"))
GOOGLE_FLOW_API = "https://aisandbox-pa.googleapis.com"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY")
FLOW_START_URL = os.getenv("FLOW_START_URL", "https://labs.google/fx/tools/flow")
API_KEY = os.getenv("API_KEY", "change-me")
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
BROWSER_PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", "./data/profile"))
STATE_DIR = Path(os.getenv("STATE_DIR", "./data/state"))
LOG_DIR = Path(os.getenv("LOG_DIR", "./data/logs"))

IMAGE_MODELS = {
    "NANO_BANANA_PRO": "GEM_PIX_2",
    "NANO_BANANA_2": "NANO_BANANA_2",
}

ENDPOINTS = {
    "generate_images": "/v1/projects/{project_id}/flowMedia:batchGenerateImages",
    "upload_image": "/v1/flow/uploadImage",
    "get_credits": "/v1/credits",
}

for directory in (BROWSER_PROFILE_DIR, STATE_DIR, LOG_DIR):
    directory.mkdir(parents=True, exist_ok=True)
