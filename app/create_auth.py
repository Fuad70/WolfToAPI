"""
Authentication creation handler for VNC-based auth generation
Adapted from AIStudioToAPI for FlowKit
"""

import asyncio
import json
import logging
import os
import re
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CreateAuth:
    """
    CreateAuth Manager
    Handles VNC session creation and auth file generation
    """

    def __init__(self, server_system):
        self.server_system = server_system
        self.logger = server_system.logger
        self.config = server_system.config
        self.vnc_session = None
        self.current_lock_token = None  # Token to identify who holds the lock
        self.current_vnc_abort_controller = None  # Controller to abort ongoing setup

    async def _run_with_signal(self, coro, signal):
        """Helper: Run a coroutine but abort immediately if the signal is aborted."""
        if signal and signal.is_set():
            raise Exception("VNC_SETUP_ABORTED")
        if not signal:
            return await coro

        task = asyncio.create_task(coro)
        abort_task = asyncio.create_task(signal.wait())

        try:
            done, pending = await asyncio.wait(
                [task, abort_task], return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
            if abort_task in done:
                raise Exception("VNC_SETUP_ABORTED")
            return task.result()
        except asyncio.CancelledError:
            raise Exception("VNC_SETUP_ABORTED")

    async def _wait_for_port(self, port: int, timeout: int = 5000, signal=None) -> None:
        """Wait for a port to become available"""
        start_time = time.time()
        while time.time() - start_time < timeout / 1000:
            if signal and signal.is_set():
                raise Exception("VNC_SETUP_ABORTED")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.settimeout(0.1)
                result = sock.connect_ex(("localhost", port))
                if result == 0:
                    return
            except:
                pass
            finally:
                sock.close()
            await asyncio.sleep(0.1)
        raise Exception(f"Timeout waiting for port {port}")

    def _reject_if_system_busy(self, res) -> bool:
        if not self.server_system.request_handler or not self.server_system.request_handler.is_system_busy:
            return False

        res.status_code = 409
        res.detail = "System is busy switching or recovering accounts. Please try again later."
        return True

    async def start_vnc_session(self, req, res) -> None:
        """Start a VNC session for authentication"""
        if os.name == "nt":  # Windows
            res.status_code = 501
            res.detail = "VNC feature is not supported on Windows."
            return

        # Concurrency Handling with Token Ownership
        my_token = object()  # Unique object identity

        if self.current_lock_token:
            self.logger.warning("[VNC] A VNC operation is already in progress. Signal interruption...")

            if self.current_vnc_abort_controller:
                self.current_vnc_abort_controller.set()

            # Wait for the previous operation to clean up and release the lock
            wait_start = time.time()
            while self.current_lock_token:
                if self.current_vnc_abort_controller:
                    self.current_vnc_abort_controller.set()

                if time.time() - wait_start > 6:
                    res.status_code = 503
                    res.detail = "Timeout waiting for previous session to abort."
                    return
                await asyncio.sleep(0.2)
            self.logger.info("[VNC] Lock acquired after previous session cleanup.")

        self.current_lock_token = my_token
        self.current_vnc_abort_controller = asyncio.Event()

        signal = self.current_vnc_abort_controller

        session_resources = {}

        try:
            # Always clean up any existing session before starting a new one
            await self._cleanup_vnc_session("new_session_request", self.vnc_session)
            await asyncio.sleep(0.2)  # Add delay to ensure OS releases ports

            user_agent = req.headers.get("user-agent", "")
            is_mobile = "Mobi" in user_agent or "Android" in user_agent
            self.logger.info(f"[VNC] Detected User-Agent: '{user_agent}'. Is mobile: {is_mobile}")

            body = await req.json()
            width = body.get("width", 412 if is_mobile else 1280)
            height = body.get("height", 915 if is_mobile else 720)
            screen_width = max(2, width // 2 * 2)  # Ensure even
            screen_height = max(2, height // 2 * 2)
            screen_resolution = f"{screen_width}x{screen_height}x24"
            self.logger.info(f"[VNC] Requested VNC resolution: {screen_width}x{screen_height}")

            vnc_port = 5901
            websockify_port = 6080
            display = ":99"

            scoped_cleanup = lambda reason: self._cleanup_vnc_session(reason, session_resources)

            self.logger.info(f"[VNC] Starting virtual screen (Xvfb) on display {display} with resolution {screen_resolution}...")
            xvfb = await asyncio.create_subprocess_exec(
                "Xvfb", display, "-screen", "0", screen_resolution, "+extension", "RANDR",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            session_resources["xvfb"] = xvfb

            # Wait for Xvfb to be ready
            await asyncio.sleep(0.5)

            self.logger.info(f"[VNC] Starting VNC server (x11vnc) on port {vnc_port}...")
            x11vnc = await asyncio.create_subprocess_exec(
                "x11vnc", "-display", display, "-rfbport", str(vnc_port), "-forever", "-nopw", "-shared", "-quiet", "-repeat",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            session_resources["x11vnc"] = x11vnc

            await self._wait_for_port(vnc_port, 30000, signal)
            self.logger.info("[VNC] VNC server is ready.")

            self.logger.info(f"[VNC] Starting websockify on port {websockify_port}...")
            websockify = await asyncio.create_subprocess_exec(
                "websockify", str(websockify_port), f"localhost:{vnc_port}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            session_resources["websockify"] = websockify

            await self._wait_for_port(websockify_port, 30000, signal)
            self.logger.info("[VNC] Websockify is ready.")

            self.logger.info("[VNC] Launching browser for VNC session...")
            browser_result = await self._run_with_signal(
                self.server_system.browser_manager.launch_browser_for_vnc({
                    "env": {"DISPLAY": display},
                    "is_mobile": is_mobile,
                }),
                signal
            )
            session_resources["browser"] = browser_result["browser"]
            session_resources["context"] = browser_result["context"]

            context = browser_result["context"]
            page = await context.new_page()

            await page.set_viewport_size({"width": screen_width, "height": screen_height})

            await page.add_init_script("""
                (function() {
                    const style = document.createElement("style");
                    style.textContent = `
                        html, body {
                            margin: 0 !important;
                            padding: 0 !important;
                            width: 100vw !important;
                            height: 100vh !important;
                            overflow: auto !important;
                        }
                    `;
                    document.addEventListener("DOMContentLoaded", () => {
                        document.head.appendChild(style);
                    });
                })();
            """)

            # Navigate to Flow instead of AI Studio
            await page.goto("https://labs.google/fx/tools/flow", timeout=120000, wait_until="domcontentloaded")
            session_resources["page"] = page

            # Set idle timeout
            session_resources["timeout_handle"] = asyncio.get_event_loop().call_later(
                10 * 60, lambda: asyncio.create_task(scoped_cleanup("idle_timeout"))
            )

            self.vnc_session = session_resources

            self.logger.info("[VNC] VNC session is live and accessible via the server's WebSocket proxy.")
            res.status_code = 200
            res.detail = {"protocol": "websocket", "success": True}

        except Exception as error:
            if "VNC_SETUP_ABORTED" in str(error):
                self.logger.warning("[VNC] Current session setup aborted by new incoming request.")
                await self._cleanup_vnc_session("setup_aborted", session_resources)
                res.status_code = 499
                res.detail = {"message": "errorVncSetupAborted"}
            else:
                self.logger.error(f"[VNC] Failed to start VNC session: {error}")
                await self._cleanup_vnc_session("startup_error", session_resources)
                res.status_code = 500
                res.detail = {"message": "errorVncStartFailed"}
        finally:
            # Only release lock if this instance holds it
            if self.current_lock_token is my_token:
                self.logger.info("[VNC] Releasing lock for current session.")
                self.current_lock_token = None
                self.current_vnc_abort_controller = None

    async def save_auth_file(self, req, res) -> None:
        """Save authentication file from current VNC session"""
        if not self.vnc_session or not self.vnc_session.get("context"):
            res.status_code = 400
            res.detail = {"message": "errorVncNoSession"}
            return

        body = await req.json()
        account_name = body.get("accountName")
        context = self.vnc_session["context"]
        page = self.vnc_session["page"]
        session_ref = self.vnc_session

        if account_name:
            self.logger.info(f"[VNC] Using provided account name: {account_name}")
        else:
            try:
                self.logger.info("[VNC] Attempting to retrieve account name by scanning <script> JSON...")
                script_elements = await page.query_selector_all('script[type="application/json"]')
                self.logger.info(f"[VNC] -> Found {len(script_elements)} JSON <script> tags.")

                email_regex = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
                found_email = False

                for script in script_elements:
                    content = await script.inner_text()
                    if content:
                        match = re.search(email_regex, content)
                        if match:
                            account_name = match.group(1)
                            self.logger.info(f"[VNC] -> Successfully retrieved account: {account_name}")
                            found_email = True
                            break

                if not found_email:
                    raise Exception(f"Iterated through all {len(script_elements)} <script> tags, but no email found.")

            except Exception as e:
                self.logger.warning(f"[VNC] Could not automatically detect email: {e.message}. Requesting manual input from client.")
                res.status_code = 400
                res.detail = {"message": "errorVncEmailFetchFailed"}
                return

        try:
            storage_state = await context.storage_state()
            auth_data = {**storage_state, "accountName": account_name}

            config_dir = Path.cwd() / "configs" / "auth"
            config_dir.mkdir(parents=True, exist_ok=True)

            # Always use max index + 1 to ensure new auth is always the latest
            existing_indices = self.server_system.auth_source.available_indices or []
            next_auth_index = max(existing_indices) + 1 if existing_indices else 0

            new_auth_file_path = config_dir / f"auth-{next_auth_index}.json"
            new_auth_file_path.write_text(json.dumps(auth_data, indent=2), encoding="utf-8")

            self.logger.info(f"[VNC] Saved new auth file: {new_auth_file_path}")

            self.server_system.auth_source.reload_auth_sources()

            res.status_code = 200
            res.detail = {
                "accountName": account_name,
                "accountNameMap": self.server_system.auth_source.account_name_map,
                "availableIndices": self.server_system.auth_source.available_indices,
                "filePath": str(new_auth_file_path),
                "message": "vncAuthSaveSuccess",
                "newAuthIndex": next_auth_index,
            }

            # Clean up session after saving
            asyncio.get_event_loop().call_later(
                0.5, lambda: asyncio.create_task(self._cleanup_vnc_session("auth_saved", session_ref))
            )

        except Exception as error:
            self.logger.error(f"[VNC] Failed to save auth file: {error}")
            res.status_code = 500
            res.detail = {"error": str(error), "message": "errorVncSaveFailed"}

    async def _cleanup_vnc_session(self, reason: str = "unknown", specific_session=None) -> None:
        """Clean up VNC session resources"""
        session_to_cleanup = specific_session or self.vnc_session

        if not session_to_cleanup:
            return

        if not specific_session:
            self.vnc_session = None
        elif self.vnc_session is session_to_cleanup:
            self.vnc_session = None

        self.logger.info(f"[VNC] Starting VNC session cleanup (Reason: {reason})...")

        browser = session_to_cleanup.get("browser")
        context = session_to_cleanup.get("context")
        xvfb = session_to_cleanup.get("xvfb")
        x11vnc = session_to_cleanup.get("x11vnc")
        websockify = session_to_cleanup.get("websockify")
        timeout_handle = session_to_cleanup.get("timeout_handle")

        if timeout_handle:
            timeout_handle.cancel()

        # Helper to race a promise against a timeout
        async def with_timeout(coro, ms):
            try:
                return await asyncio.wait_for(coro, timeout=ms / 1000)
            except asyncio.TimeoutError:
                pass

        try:
            if browser:
                await with_timeout(browser.close(), 2000)
            elif context:
                await with_timeout(context.close(), 2000)
        except Exception as e:
            self.logger.info(f"[VNC] Browser/Context close timed out or failed: {e}. Proceeding to force kill.")

        # Kill processes
        for proc_name, proc in [("xvfb", xvfb), ("x11vnc", x11vnc), ("websockify", websockify)]:
            if proc and not proc.returncode:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except:
                    try:
                        proc.kill()
                        await asyncio.wait_for(proc.wait(), timeout=1)
                    except:
                        pass