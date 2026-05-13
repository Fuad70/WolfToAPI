from __future__ import annotations

import asyncio
import base64
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import websockets
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from .config import AGENT_WS_PORT, APP_PORT, CORS_ORIGINS, LOG_LEVEL
from .flow_bridge import (
    bridge,
    extract_image_url,
    map_aspect_ratio,
    openai_model_to_flow,
    size_to_aspect_ratio,
    upload_media_id,
)
from .models import EditRequest, GenerateRequest, OpenAIImageRequest
from .security import require_api_key
from .auth_source import AuthSource
from .auth_switcher import AuthSwitcher
from .browser_manager import BrowserManager
from .create_auth import CreateAuth
from .proxy_server_system import ProxyServerSystem
from .request_handler import RequestHandler

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("flowkit-selfhost")
CALLBACK_SECRET = secrets.token_urlsafe(24)
STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


async def ws_handler(websocket):
    bridge.set_extension(websocket)
    await bridge.set_callback_secret(CALLBACK_SECRET)
    try:
        async for raw in websocket:
            try:
                await bridge.handle_message(__import__("json").loads(raw))
            except Exception as exc:  # noqa: BLE001
                logger.exception("WebSocket message error: %s", exc)
    except websockets.ConnectionClosed:
        pass
    finally:
        bridge.clear_extension()


async def run_ws_server():
    async with websockets.serve(ws_handler, "0.0.0.0", AGENT_WS_PORT):
        await asyncio.Future()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize server system
    server_system = ProxyServerSystem(logger)
    await server_system.initialize()

    # Store in app state for access in routes
    app.state.server_system = server_system

    ws_task = asyncio.create_task(run_ws_server())
    logger.info("HTTP on :%s, extension WS on :%s", APP_PORT, AGENT_WS_PORT)
    yield
    ws_task.cancel()
    await server_system.shutdown()


app = FastAPI(title="FlowKit Flow Selfhost", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(STATIC_INDEX)


@app.get("/health")
async def health():
    status = await bridge.get_status() if bridge.connected else {"connected": False, "flow_key_present": False, "extension": {}}
    return {"status": "ok", "extension_connected": bridge.connected, "flow_key_present": bridge.flow_key_present, "details": status}


@app.get("/api/status")
async def status():
    return await health()


@app.post("/api/ext/callback")
async def ext_callback(request: Request):
    if request.headers.get("x-flowkit-secret") != CALLBACK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid callback secret")
    data = await request.json()
    req_id = data.get("id")
    if not req_id or req_id not in bridge._pending:
        return {"ok": False}
    future = bridge._pending[req_id]
    if not future.done():
        future.set_result(data)
    return {"ok": True}


@app.post("/api/browser/open-flow")
async def open_flow(_: bool = Depends(require_api_key)):
    result = await bridge.open_flow()
    return {"ok": not result.get("error"), "result": result}


@app.post("/api/generate")
async def generate_image(body: GenerateRequest, _: bool = Depends(require_api_key)):
    if not bridge.connected:
        raise HTTPException(status_code=503, detail="Browser extension not connected yet")
    result = await bridge.generate_images(body.prompt, map_aspect_ratio(body.aspect_ratio), body.image_model)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    image_url = extract_image_url(result)
    if not image_url:
        raise HTTPException(status_code=500, detail=f"No image URL found in response: {str(result)[:500]}")
    return {"url": image_url, "raw": result}


async def _download_image(url: str) -> tuple[bytes, str]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download source image: {response.status}")
            return await response.read(), response.headers.get("content-type", "image/jpeg")


@app.post("/api/edit")
async def edit_image(body: EditRequest, _: bool = Depends(require_api_key)):
    if not bridge.connected:
        raise HTTPException(status_code=503, detail="Browser extension not connected yet")
    image_bytes, mime_type = await _download_image(body.image_url)
    project_id = __import__("uuid").uuid4().hex
    upload_result = await bridge.upload_image(base64.b64encode(image_bytes).decode(), mime_type, f"edit-{project_id}.jpg", project_id)
    if upload_result.get("error"):
        raise HTTPException(status_code=500, detail=f"Upload failed: {upload_result['error']}")
    source_media_id = upload_media_id(upload_result)
    if not source_media_id:
        raise HTTPException(status_code=500, detail=f"Upload did not return media id: {str(upload_result)[:500]}")
    result = await bridge.edit_image(body.prompt, source_media_id, map_aspect_ratio(body.aspect_ratio), body.image_model)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    image_url = extract_image_url(result)
    if not image_url:
        raise HTTPException(status_code=500, detail=f"No image URL found in response: {str(result)[:500]}")
    return {"url": image_url, "raw": result}


@app.post("/v1/images/generations")
async def openai_images(body: OpenAIImageRequest, _: bool = Depends(require_api_key)):
    if body.response_format != "url":
        raise HTTPException(status_code=400, detail="Only response_format='url' is supported in this build")
    result = await bridge.generate_images(body.prompt, map_aspect_ratio(size_to_aspect_ratio(body.size)), openai_model_to_flow(body.model))
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    image_url = extract_image_url(result)
    if not image_url:
        raise HTTPException(status_code=500, detail=f"No image URL found in response: {str(result)[:500]}")
    return {"created": int(__import__("time").time()), "data": [{"url": image_url, "revised_prompt": None}]}


# Auth routes (adapted from AIStudioToAPI)


@app.get("/login")
async def login_page():
    """Serve the login page"""
    return FileResponse(STATIC_INDEX)


@app.get("/api/auth/config")
async def auth_config():
    """Get auth configuration for frontend"""
    # For now, simple config - can be extended
    return {"requirePassword": True, "requireUsername": False}


@app.post("/login")
async def login(request: Request):
    """Handle login"""
    # Simple login implementation - can be extended
    body = await request.json()
    password = body.get("password") or body.get("apiKey")
    expected_password = os.getenv("WEB_CONSOLE_PASSWORD", "admin")

    if password == expected_password:
        # In a real implementation, you'd set session cookies
        return {"success": True}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/vnc/sessions")
async def start_vnc_session(request: Request):
    """Start VNC session for auth creation"""
    server_system = request.app.state.server_system
    if server_system.create_auth._reject_if_system_busy(None):
        raise HTTPException(status_code=409, detail="System is busy")
    await server_system.create_auth.start_vnc_session(request, type('Response', (), {'status_code': 200, 'detail': None})())
    return {"status": "VNC session started"}


@app.post("/api/vnc/auth")
async def save_vnc_auth(request: Request):
    """Save auth from VNC session"""
    server_system = request.app.state.server_system
    response = type('Response', (), {'status_code': 200, 'detail': None})()
    await server_system.create_auth.save_auth_file(request, response)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.detail)
    return response.detail
