"""
Request Handler for FlowKit
Adapted from AIStudioToAPI for FlowKit's architecture
"""

import logging
from typing import Optional

from .auth_source import AuthSource
from .browser_manager import BrowserManager


class RequestHandler:
    """
    Request Handler for FlowKit
    Manages requests and auth switching
    """

    def __init__(self, server_system, logger: logging.Logger, browser_manager: BrowserManager, config: dict, auth_source: AuthSource):
        self.server_system = server_system
        self.logger = logger
        self.browser_manager = browser_manager
        self.config = config
        self.auth_source = auth_source

        self.auth_switcher = None  # Will be set later
        self.is_system_busy = False

    @property
    def current_auth_index(self) -> Optional[int]:
        return self.auth_switcher.current_auth_index if self.auth_switcher else None

    @property
    def failure_count(self) -> int:
        return self.auth_switcher.failure_count if self.auth_switcher else 0

    @property
    def usage_count(self) -> int:
        return self.auth_switcher.usage_count if self.auth_switcher else 0

    def get_account_name(self, auth_index: Optional[int]) -> Optional[str]:
        """Get account name for auth index"""
        if auth_index is None:
            return None
        return self.auth_source.account_name_map.get(auth_index)

    async def switch_to_next_auth(self):
        """Switch to next auth"""
        if self.auth_switcher:
            return await self.auth_switcher.switch_to_next_auth()
        return {"error": "No auth switcher configured"}

    async def switch_to_specific_auth(self, target_index: int):
        """Switch to specific auth"""
        if self.auth_switcher:
            return await self.auth_switcher.switch_to_specific_auth(target_index)
        return {"error": "No auth switcher configured"}