"""
Browser Manager for FlowKit
Adapted from AIStudioToAPI for FlowKit's simpler architecture
"""

import asyncio
import logging
from typing import Dict, Optional

from playwright.async_api import async_playwright

from .flow_bridge import FlowBridge


class BrowserManager:
    """
    Browser Manager for FlowKit
    Manages browser contexts and integration with FlowBridge
    """

    def __init__(self, logger: logging.Logger, config: dict, auth_source):
        self.logger = logger
        self.config = config
        self.auth_source = auth_source
        self.auth_switcher = None  # Will be set later

        self.browser = None
        self.contexts: Dict[int, Dict] = {}  # auth_index -> {context, page, health_monitor}
        self._current_auth_index: Optional[int] = None

    async def launch_browser_for_vnc(self, options: dict) -> Dict:
        """Launch browser for VNC session"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                f"--display={options.get('env', {}).get('DISPLAY', ':99')}",
            ],
            env=options.get("env", {}),
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        return {"browser": browser, "context": context}

    async def launch_context(self, auth_index: int) -> bool:
        """Launch a browser context for the given auth index"""
        if auth_index not in self.auth_source.available_indices:
            self.logger.error(f"[Browser] Cannot launch context for invalid auth index: {auth_index}")
            return False

        try:
            # For FlowKit, we use a single browser instance
            if not self.browser:
                playwright = await async_playwright().start()
                self.browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ]
                )

            # Create context with auth data
            auth_data = self.auth_source.get_auth(auth_index)
            if not auth_data:
                self.logger.error(f"[Browser] No auth data found for index {auth_index}")
                return False

            context = await self.browser.new_context(storage_state=auth_data)

            # Create a page and navigate to Flow to establish session
            page = await context.new_page()
            await page.goto("https://labs.google/fx/tools/flow", wait_until="domcontentloaded", timeout=30000)

            # Store context info
            self.contexts[auth_index] = {
                "context": context,
                "page": page,
                "auth_index": auth_index,
            }

            self._current_auth_index = auth_index
            self.logger.info(f"[Browser] Successfully launched context for auth #{auth_index}")
            return True

        except Exception as e:
            self.logger.error(f"[Browser] Failed to launch context for auth #{auth_index}: {e}")
            return False

    async def close_context(self, auth_index: int):
        """Close a specific browser context"""
        if auth_index in self.contexts:
            context_data = self.contexts[auth_index]
            try:
                await context_data["context"].close()
            except Exception as e:
                self.logger.warning(f"[Browser] Error closing context for auth #{auth_index}: {e}")
            del self.contexts[auth_index]

            if self._current_auth_index == auth_index:
                self._current_auth_index = None

    async def close_all_contexts(self):
        """Close all browser contexts"""
        for auth_index in list(self.contexts.keys()):
            await self.close_context(auth_index)

        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                self.logger.warning(f"[Browser] Error closing browser: {e}")
            self.browser = None

    async def rebalance_context_pool(self):
        """Rebalance the context pool based on available auths"""
        # For FlowKit's simpler architecture, just ensure we have a context for current auth
        if self.auth_switcher and self.auth_switcher.current_auth_index:
            current_auth = self.auth_switcher.current_auth_index
            if current_auth not in self.contexts:
                await self.launch_context(current_auth)

    @property
    def current_auth_index(self) -> Optional[int]:
        return self._current_auth_index

    def get_context(self, auth_index: int):
        """Get context for auth index"""
        return self.contexts.get(auth_index, {}).get("context")

    def get_page(self, auth_index: int):
        """Get page for auth index"""
        return self.contexts.get(auth_index, {}).get("page")