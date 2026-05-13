"""
Authentication switcher for account management
Adapted from AIStudioToAPI for FlowKit
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AuthSwitcher:
    """
    Auth Switcher Manager
    Handles account switching based on usage, failures, and configuration
    """

    def __init__(self, logger: logging.Logger, config: dict, auth_source, browser_manager):
        self.logger = logger
        self.config = config
        self.auth_source = auth_source
        self.browser_manager = browser_manager

        self.current_auth_index: Optional[int] = None
        self.failure_count = 0
        self.usage_count = 0
        self.is_system_busy = False

        # Configuration from env
        self.switch_on_uses = int(self.config.get("SWITCH_ON_USES", 40))
        self.failure_threshold = int(self.config.get("FAILURE_THRESHOLD", 3))
        self.immediate_switch_status_codes = set(
            int(code) for code in self.config.get("IMMEDIATE_SWITCH_STATUS_CODES", "429,503").split(",")
        )

    @property
    def current_auth_index(self) -> Optional[int]:
        return self._current_auth_index

    @current_auth_index.setter
    def current_auth_index(self, value: Optional[int]):
        self._current_auth_index = value

    def increment_usage_count(self) -> int:
        """Increment and return the usage count"""
        self.usage_count += 1
        return self.usage_count

    def should_switch_by_usage(self) -> bool:
        """Check if we should switch based on usage count"""
        return self.usage_count >= self.switch_on_uses

    def should_switch_by_failure(self, status_code: Optional[int] = None) -> bool:
        """Check if we should switch based on failure count or status code"""
        if status_code and status_code in self.immediate_switch_status_codes:
            self.logger.warning(f"[Auth] Immediate switch triggered by status code: {status_code}")
            return True
        return self.failure_count >= self.failure_threshold

    async def switch_to_next_auth(self) -> dict:
        """
        Switch to the next available auth in rotation
        """
        if self.is_system_busy:
            return {"error": "System is busy switching accounts"}

        available = self.auth_source.get_rotation_indices()
        if not available:
            return {"error": "No available auth sources for rotation"}

        current_canonical = (
            self.auth_source.get_canonical_index(self.current_auth_index)
            if self.current_auth_index is not None
            else None
        )

        # Find next index after current canonical
        try:
            current_idx = available.index(current_canonical) if current_canonical in available else -1
            next_idx = (current_idx + 1) % len(available)
            target_index = available[next_idx]
        except ValueError:
            target_index = available[0]

        return await self.switch_to_specific_auth(target_index)

    async def switch_to_specific_auth(self, target_index: int) -> dict:
        """
        Switch to a specific auth index
        """
        if self.is_system_busy:
            return {"error": "System is busy switching accounts"}

        if target_index not in self.auth_source.available_indices:
            return {"error": f"Invalid auth index: {target_index}"}

        canonical_index = self.auth_source.get_canonical_index(target_index)
        if canonical_index != target_index:
            self.logger.info(f"[Auth] Switching to canonical auth #{canonical_index} (requested #{target_index})")

        duplicate_groups = self.auth_source.get_duplicate_groups()
        expired_indices = self.auth_source.expired_indices

        # Check if target is in removal priority (duplicates or expired)
        removal_priority = set()
        for group in duplicate_groups:
            removal_priority.update(group["removed_indices"])
        removal_priority.update(expired_indices)

        # If switching to a duplicate/expired, prefer to switch to canonical instead
        if target_index in removal_priority and canonical_index != target_index:
            self.logger.info(f"[Auth] Redirecting switch from duplicate/expired #{target_index} to canonical #{canonical_index}")
            target_index = canonical_index

        # Prevent switching to self
        if target_index == self.current_auth_index:
            return {"error": f"Already using auth #{target_index}"}

        self.logger.info(f"[Auth] Switching from auth #{self.current_auth_index} to #{target_index}...")

        try:
            self.is_system_busy = True

            # Close existing context if any
            if self.current_auth_index is not None:
                await self.browser_manager.close_context(self.current_auth_index)

            # Launch new context
            success = await self.browser_manager.launch_context(target_index)
            if not success:
                self.is_system_busy = False
                return {"error": f"Failed to launch context for auth #{target_index}"}

            old_auth = self.current_auth_index
            self.current_auth_index = target_index
            self.usage_count = 0  # Reset usage count on successful switch
            self.failure_count = 0  # Reset failure count

            self.logger.info(f"[Auth] ✅ Successfully switched from #{old_auth} to #{target_index}")

            # Rebalance contexts after switch
            await self.browser_manager.rebalance_context_pool()

            return {
                "success": True,
                "old_auth": old_auth,
                "new_auth": target_index,
                "canonical_auth": canonical_index,
            }

        except Exception as e:
            self.logger.error(f"[Auth] ❌ Switch to auth #{target_index} failed: {e}")
            self.is_system_busy = False
            return {"error": str(e)}
        finally:
            self.is_system_busy = False

    async def handle_request_failure_and_switch(self, error_message: str, status_code: Optional[int] = None) -> dict:
        """
        Handle request failure and potentially switch accounts
        """
        self.failure_count += 1

        should_switch = self.should_switch_by_failure(status_code)
        if not should_switch:
            self.logger.warning(f"[Auth] Request failed (count: {self.failure_count}/{self.failure_threshold}): {error_message}")
            return {"switched": False, "failure_count": self.failure_count}

        self.logger.warning(f"[Auth] Failure threshold reached ({self.failure_count}/{self.failure_threshold}). Triggering account switch.")

        switch_result = await self.switch_to_next_auth()
        if switch_result.get("success"):
            return {
                "switched": True,
                "old_auth": switch_result.get("old_auth"),
                "new_auth": switch_result.get("new_auth"),
                "reason": "failure_threshold",
            }
        else:
            self.logger.error(f"[Auth] Failed to switch after reaching failure threshold: {switch_result.get('error')}")
            return {"switched": False, "error": switch_result.get("error")}

    def reset_failure_count(self):
        """Reset the failure count (typically after a successful request)"""
        if self.failure_count > 0:
            self.logger.info(f"[Auth] ✅ Request successful - failure count reset from {self.failure_count} to 0")
            self.failure_count = 0