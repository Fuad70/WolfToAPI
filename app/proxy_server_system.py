"""
Proxy Server System for FlowKit
Adapted from AIStudioToAPI's ProxyServerSystem
"""

import logging
import os
from typing import Dict, Optional

from .auth_source import AuthSource
from .auth_switcher import AuthSwitcher
from .browser_manager import BrowserManager
from .config import *
from .create_auth import CreateAuth
from .request_handler import RequestHandler


class ProxyServerSystem:
    """
    Main server system that coordinates all components
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.config = self._load_config()

        # Initialize core components
        self.auth_source = AuthSource(logger)
        self.browser_manager = BrowserManager(logger, self.config, self.auth_source)
        self.auth_switcher = AuthSwitcher(logger, self.config, self.auth_source, self.browser_manager)
        self.request_handler = RequestHandler(self, logger, self.browser_manager, self.config, self.auth_source)
        self.create_auth = CreateAuth(self)

        # Update browser manager with auth switcher
        self.browser_manager.auth_switcher = self.auth_switcher

    def _load_config(self) -> Dict:
        """Load configuration from environment variables"""
        return {
            "API_KEYS": os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else [],
            "INITIAL_AUTH_INDEX": int(os.getenv("INITIAL_AUTH_INDEX", "0")),
            "SWITCH_ON_USES": int(os.getenv("SWITCH_ON_USES", "40")),
            "FAILURE_THRESHOLD": int(os.getenv("FAILURE_THRESHOLD", "3")),
            "IMMEDIATE_SWITCH_STATUS_CODES": os.getenv("IMMEDIATE_SWITCH_STATUS_CODES", "429,503"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
            "MAX_CONTEXTS": int(os.getenv("MAX_CONTEXTS", "1")),
            "WEB_CONSOLE_USERNAME": os.getenv("WEB_CONSOLE_USERNAME"),
            "WEB_CONSOLE_PASSWORD": os.getenv("WEB_CONSOLE_PASSWORD"),
        }

    async def initialize(self):
        """Initialize the server system"""
        self.logger.info("[System] Initializing FlowKit server system...")

        # Launch initial browser context if auth sources exist
        if self.auth_source.available_indices:
            initial_auth = self.config["INITIAL_AUTH_INDEX"]
            if initial_auth in self.auth_source.available_indices:
                self.logger.info(f"[System] Launching initial browser context for auth #{initial_auth}")
                await self.browser_manager.launch_context(initial_auth)
                self.auth_switcher.current_auth_index = initial_auth
            else:
                self.logger.warning(f"[System] Initial auth index #{initial_auth} not available, starting with first available")
                first_auth = self.auth_source.available_indices[0]
                await self.browser_manager.launch_context(first_auth)
                self.auth_switcher.current_auth_index = first_auth

        self.logger.info("[System] FlowKit server system initialized")

    async def shutdown(self):
        """Shutdown the server system"""
        self.logger.info("[System] Shutting down FlowKit server system...")
        await self.browser_manager.close_all_contexts()
        self.logger.info("[System] FlowKit server system shutdown complete")