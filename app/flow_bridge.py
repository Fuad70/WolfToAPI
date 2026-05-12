from __future__ import annotations

import asyncio
import copy
import json
import random
import re
import time
import uuid
from typing import Any

from .config import ENDPOINTS, GOOGLE_API_KEY, GOOGLE_FLOW_API, IMAGE_MODELS

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
]


class FlowBridge:
    def __init__(self):
        self._extension_ws = None
        self._pending: dict[str, asyncio.Future] = {}
        self._flow_key: str | None = None
        self._callback_secret: str | None = None
        self._connected_at: float | None = None
        self._lock = asyncio.Lock()

    def set_extension(self, websocket):
        self._extension_ws = websocket
        self._connected_at = time.time()

    def clear_extension(self):
        self._extension_ws = None
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(ConnectionError("Extension disconnected"))
        self._pending.clear()

    @property
    def connected(self) -> bool:
        return self._extension_ws is not None

    @property
    def flow_key_present(self) -> bool:
        return bool(self._flow_key)

    async def handle_message(self, data: dict[str, Any]):
        msg_type = data.get("type")
        if msg_type == "token_captured":
            self._flow_key = data.get("flowKey")
            return
        if msg_type == "extension_ready":
            return
        if msg_type == "pong":
            return
        req_id = data.get("id")
        if req_id and req_id in self._pending and not self._pending[req_id].done():
            self._pending[req_id].set_result(data)

    async def set_callback_secret(self, secret: str):
        self._callback_secret = secret
        if self.connected:
            await self._extension_ws.send(json.dumps({"type": "callback_secret", "secret": secret}))

    def _build_url(self, endpoint_key: str, **kwargs) -> str:
        path = ENDPOINTS[endpoint_key].format(**kwargs)
        sep = "&" if "?" in path else "?"
        return f"{GOOGLE_FLOW_API}{path}{sep}key={GOOGLE_API_KEY}"

    def _headers(self) -> dict[str, str]:
        ua = random.choice(_USER_AGENTS)
        platform = '"Windows"' if "Windows" in ua else ('"macOS"' if "Macintosh" in ua else '"Linux"')
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "content-type": "text/plain;charset=UTF-8",
            "origin": "https://labs.google",
            "referer": "https://labs.google/",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Chromium";v="141", "Google Chrome";v="141"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": ua,
            "x-browser-channel": "stable",
            "x-browser-copyright": "Copyright 2025 Google LLC. All rights reserved.",
            "x-browser-validation": "SgDQo8mvrGRdD61Pwo8wyWVgYgs=",
            "x-browser-year": "2025",
            "x-client-data": "CKi1yQEIh7bJAQiktskBCKmdygEIvorLAQiUocsBCIagzQEYv6nKARjRp88BGKqwzwE=",
        }

    async def _send(self, method: str, params: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
        if not self._extension_ws:
            return {"error": "Extension not connected"}
        req_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        try:
            async with self._lock:
                await self._extension_ws.send(json.dumps({"id": req_id, "method": method, "params": params}))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Timeout waiting for {method}"}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            self._pending.pop(req_id, None)

    def _client_context(self, project_id: str, user_paygate_tier: str = "PAYGATE_TIER_TWO") -> dict[str, Any]:
        return {
            "projectId": project_id,
            "recaptchaContext": {
                "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB",
                "token": "",
            },
            "sessionId": f";{int(time.time() * 1000)}",
            "tool": "PINHOLE",
            "userPaygateTier": user_paygate_tier,
        }

    async def get_status(self) -> dict[str, Any]:
        result = await self._send("get_status", {}, timeout=20)
        payload = result.get("result", {}) if isinstance(result, dict) else {}
        return {
            "connected": self.connected,
            "flow_key_present": self.flow_key_present,
            "extension": payload,
            "uptime_s": int(time.time() - self._connected_at) if self._connected_at and self.connected else None,
        }

    async def open_flow(self) -> dict[str, Any]:
        return await self._send("open_flow", {}, timeout=20)

    async def get_credits(self) -> dict[str, Any]:
        return await self._send(
            "api_request",
            {
                "url": self._build_url("get_credits"),
                "method": "GET",
                "headers": self._headers(),
            },
            timeout=60,
        )

    async def generate_images(self, prompt: str, aspect_ratio: str, image_model: str | None = None) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        ctx = self._client_context(project_id)
        ts = int(time.time() * 1000)
        model_name = IMAGE_MODELS.get(image_model or "", IMAGE_MODELS["NANO_BANANA_PRO"])
        body = {
            "clientContext": ctx,
            "requests": [
                {
                    "clientContext": {**ctx, "sessionId": f";{ts}"},
                    "seed": ts % 1000000,
                    "structuredPrompt": {"parts": [{"text": prompt}]},
                    "imageAspectRatio": aspect_ratio,
                    "imageModelName": model_name,
                }
            ],
        }
        return await self._send(
            "api_request",
            {
                "url": self._build_url("generate_images", project_id=project_id),
                "method": "POST",
                "headers": self._headers(),
                "body": body,
                "captchaAction": "IMAGE_GENERATION",
            },
            timeout=240,
        )

    async def upload_image(self, image_base64: str, mime_type: str, file_name: str, project_id: str) -> dict[str, Any]:
        body = {
            "clientContext": self._client_context(project_id),
            "filename": file_name,
            "mimeType": mime_type,
            "imageBytesBase64Encoded": image_base64,
        }
        return await self._send(
            "api_request",
            {
                "url": self._build_url("upload_image"),
                "method": "POST",
                "headers": self._headers(),
                "body": body,
                "captchaAction": "IMAGE_GENERATION",
            },
            timeout=240,
        )

    async def edit_image(self, prompt: str, source_media_id: str, aspect_ratio: str, image_model: str | None = None) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        ctx = self._client_context(project_id)
        ts = int(time.time() * 1000)
        model_name = IMAGE_MODELS.get(image_model or "", IMAGE_MODELS["NANO_BANANA_PRO"])
        body = {
            "clientContext": ctx,
            "mediaGenerationContext": {"batchId": str(uuid.uuid4())},
            "useNewMedia": True,
            "requests": [
                {
                    "clientContext": {**ctx, "sessionId": f";{ts}"},
                    "seed": ts % 1000000,
                    "structuredPrompt": {"parts": [{"text": prompt}]},
                    "imageAspectRatio": aspect_ratio,
                    "imageModelName": model_name,
                    "imageInputs": [
                        {"name": source_media_id, "imageInputType": "IMAGE_INPUT_TYPE_BASE_IMAGE"}
                    ],
                }
            ],
        }
        return await self._send(
            "api_request",
            {
                "url": self._build_url("generate_images", project_id=project_id),
                "method": "POST",
                "headers": self._headers(),
                "body": body,
                "captchaAction": "IMAGE_GENERATION",
            },
            timeout=240,
        )


bridge = FlowBridge()


def map_aspect_ratio(value: str) -> str:
    mapping = {
        "16:9": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "9:16": "IMAGE_ASPECT_RATIO_PORTRAIT",
        "1:1": "IMAGE_ASPECT_RATIO_SQUARE",
        "4:3": "IMAGE_ASPECT_RATIO_LANDSCAPE",
        "3:4": "IMAGE_ASPECT_RATIO_PORTRAIT",
    }
    return mapping.get(value, "IMAGE_ASPECT_RATIO_LANDSCAPE")


def size_to_aspect_ratio(size: str) -> str:
    match = re.match(r"^(\d+)x(\d+)$", size or "")
    if not match:
        return "16:9"
    width = int(match.group(1))
    height = int(match.group(2))
    ratio = width / height if height else 1
    if 0.9 <= ratio <= 1.1:
        return "1:1"
    if ratio < 0.8:
        return "9:16"
    if ratio < 1.5:
        return "4:3"
    return "16:9"


def openai_model_to_flow(model: str) -> str:
    value = (model or "").lower()
    if "banana-2" in value:
        return "NANO_BANANA_2"
    return "NANO_BANANA_PRO"


def extract_image_url(result: dict[str, Any]) -> str | None:
    data = result.get("data", result)
    if not isinstance(data, dict):
        return None
    for media in data.get("media", []):
        image_obj = media.get("image", {})
        for candidate in (image_obj.get("fifeUrl"), image_obj.get("generatedImage", {}).get("fifeUrl")):
            if candidate:
                return candidate
    return None


def upload_media_id(result: dict[str, Any]) -> str | None:
    if result.get("_mediaId"):
        return result["_mediaId"]
    data = result.get("data", result)
    if isinstance(data, dict):
        return data.get("name") or data.get("mediaId")
    return None
