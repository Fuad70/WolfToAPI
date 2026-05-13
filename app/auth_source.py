"""
Authentication source manager that loads and validates authentication data from config files
Adapted from AIStudioToAPI for FlowKit
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class AuthSource:
    """
    Authentication Source Management Module
    Responsible for loading and managing authentication information from the file system
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.auth_mode = "file"
        self.available_indices: List[int] = []
        # Indices used for rotation/switching (deduplicated by email, keeping the latest index per account)
        self.rotation_indices: List[int] = []
        # Duplicate auth indices detected (valid JSON but skipped from rotation due to same email)
        self.duplicate_indices: List[int] = []
        # Expired auth indices (valid JSON but marked as expired, excluded from rotation)
        self.expired_indices: List[int] = []
        self.initial_indices: List[int] = []
        self.account_name_map: Dict[int, Optional[str]] = {}
        # Map any valid index -> canonical (latest) index for the same account email
        self.canonical_index_map: Dict[int, int] = {}
        # Duplicate groups (email -> kept + duplicates)
        self.duplicate_groups: List[Dict] = []
        self.last_scanned_indices = "[]"  # Cache to track changes

        self.logger.info('[Auth] Using files in "configs/auth/" directory for authentication.')

        self.reload_auth_sources(True)  # Initial load

        if not self.available_indices:
            self.logger.warning(
                "[Auth] No valid authentication sources found in 'file' mode. The server will start in account binding mode."
            )

    def reload_auth_sources(self, is_initial_load: bool = False) -> bool:
        old_indices = self.last_scanned_indices
        self._discover_available_indices()
        new_indices = json.dumps(sorted(self.initial_indices))

        # Only log verbosely if it's the first load or if the file list has actually changed.
        if is_initial_load or old_indices != new_indices:
            self.logger.info("[Auth] Auth file scan detected changes. Reloading and re-validating...")
            self._pre_validate_and_filter()
            self.logger.info(
                f"[Auth] Reload complete. {len(self.available_indices)} valid sources available: [{', '.join(map(str, self.available_indices))}]"
            )
            self.last_scanned_indices = new_indices
            return True  # Changes detected
        return False  # No changes

    def remove_auth(self, index: int) -> Dict:
        if not isinstance(index, int):
            raise ValueError("Invalid account index.")

        auth_file_path = Path.cwd() / "configs" / "auth" / f"auth-{index}.json"
        if not auth_file_path.exists():
            raise ValueError(f"Auth file for account #{index} does not exist.")

        try:
            auth_file_path.unlink()
        except Exception as error:
            raise ValueError(f"Failed to delete auth file for account #{index}: {error}")

        return {
            "remaining_accounts": len(self.available_indices),
            "removed_index": index,
        }

    def _discover_available_indices(self):
        indices = []
        config_dir = Path.cwd() / "configs" / "auth"
        if not config_dir.exists():
            self.available_indices = []
            self.initial_indices = []
            return

        try:
            auth_files = [f for f in config_dir.iterdir() if f.name.match(r"^auth-\d+\.json$")]
            indices = [int(f.name.split("-")[1].split(".")[0]) for f in auth_files]
        except Exception as error:
            self.logger.error(f"[Auth] Failed to scan 'configs/auth/' directory: {error}")
            self.available_indices = []
            self.initial_indices = []
            return

        self.initial_indices = sorted(list(set(indices)))

    def _pre_validate_and_filter(self):
        if not self.initial_indices:
            self.available_indices = []
            self.rotation_indices = []
            self.duplicate_indices = []
            self.expired_indices = []
            self.account_name_map.clear()
            self.canonical_index_map.clear()
            self.duplicate_groups = []
            return

        valid_indices = []
        invalid_source_descriptions = []
        self.account_name_map.clear()  # Clear old names before re-validating
        self.canonical_index_map.clear()
        self.duplicate_groups = []
        self.expired_indices = []

        for index in self.initial_indices:
            # Iterate over initial to check all, not just previously available
            auth_content = self._get_auth_content(index)
            if auth_content:
                try:
                    auth_data = json.loads(auth_content)
                    valid_indices.append(index)
                    self.account_name_map[index] = auth_data.get("accountName")
                    # Track expired status from auth file
                    if auth_data.get("expired") is True:
                        self.expired_indices.append(index)
                except json.JSONDecodeError:
                    invalid_source_descriptions.append(f"auth-{index} (parse error)")
            else:
                invalid_source_descriptions.append(f"auth-{index} (unreadable)")

        if invalid_source_descriptions:
            self.logger.warning(
                f"⚠️ [Auth] Pre-validation found {len(invalid_source_descriptions)} authentication sources with format errors or unreadable: [{', '.join(invalid_source_descriptions)}], will be removed from available list."
            )

        self.available_indices = sorted(valid_indices)
        self._build_rotation_indices()

    def _normalize_email_key(self, account_name: Optional[str]) -> Optional[str]:
        if not isinstance(account_name, str):
            return None
        trimmed = account_name.strip()
        if not trimmed:
            return None
        # Conservative: only deduplicate when the name looks like an email address.
        import re
        email_pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(email_pattern, trimmed):
            return None
        return trimmed.lower()

    def _build_rotation_indices(self):
        self.rotation_indices = []
        self.duplicate_indices = []
        self.duplicate_groups = []
        self.canonical_index_map.clear()

        email_key_to_indices: Dict[str, List[int]] = {}

        # Only process non-expired accounts for rotation and deduplication
        non_expired_indices = [idx for idx in self.available_indices if idx not in self.expired_indices]

        for index in non_expired_indices:
            account_name = self.account_name_map.get(index)
            email_key = self._normalize_email_key(account_name)

            if not email_key:
                self.rotation_indices.append(index)
                self.canonical_index_map[index] = index
                continue

            if email_key not in email_key_to_indices:
                email_key_to_indices[email_key] = []
            email_key_to_indices[email_key].append(index)

        for email_key, indices in email_key_to_indices.items():
            indices.sort()
            kept_index = indices[-1]  # Latest index
            self.rotation_indices.append(kept_index)

            duplicate_indices = []
            for index in indices:
                self.canonical_index_map[index] = kept_index
                if index != kept_index:
                    duplicate_indices.append(index)

            if duplicate_indices:
                self.duplicate_indices.extend(duplicate_indices)
                self.duplicate_groups.append({
                    "email": email_key,
                    "kept_index": kept_index,
                    "removed_indices": duplicate_indices,
                })

        self.rotation_indices = sorted(list(set(self.rotation_indices)))

        if self.duplicate_indices:
            self.logger.info(
                f"[Auth] Detected {len(self.duplicate_indices)} duplicate auth files (same email). "
                f"Keeping latest: [{', '.join(str(idx) for idx in self.duplicate_indices)}] will be skipped in rotation."
            )

        if self.expired_indices:
            self.logger.info(
                f"[Auth] Detected {len(self.expired_indices)} expired auth files: [{', '.join(map(str, self.expired_indices))}]. "
                "Excluded from rotation."
            )

    def _get_auth_content(self, index: int) -> Optional[str]:
        auth_file_path = Path.cwd() / "configs" / "auth" / f"auth-{index}.json"
        if not auth_file_path.exists():
            return None
        try:
            return auth_file_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def get_auth(self, index: int) -> Optional[Dict]:
        if index not in self.available_indices:
            self.logger.error(f"[Auth] Requested invalid or non-existent authentication index: {index}")
            return None

        json_string = self._get_auth_content(index)
        if not json_string:
            self.logger.error(f"[Auth] Unable to retrieve content for authentication source #{index} during read.")
            return None

        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            self.logger.error(f"[Auth] Failed to parse JSON content from authentication source #{index}: {e}")
            return None

    async def mark_as_expired(self, index: int) -> bool:
        """
        Mark an auth as expired
        - Adds "expired": true to the auth file (configs/auth/auth-{index}.json)
        - Rebuilds rotation indices to exclude the expired account from rotation
        """
        if index not in self.available_indices:
            self.logger.warning(f"[Auth] Cannot mark non-existent auth #{index} as expired")
            return False

        if index in self.expired_indices:
            self.logger.debug(f"[Auth] Auth #{index} is already marked as expired")
            return False

        auth_file_path = Path.cwd() / "configs" / "auth" / f"auth-{index}.json"

        try:
            file_content = await Path(auth_file_path).read_text(encoding="utf-8")
            auth_data = json.loads(file_content)
            auth_data["expired"] = True
            await Path(auth_file_path).write_text(json.dumps(auth_data, indent=2), encoding="utf-8")

            # Rebuild rotation indices to exclude this expired account
            self._build_rotation_indices()

            self.logger.warning(f"[Auth] ⏰ Marked auth #{index} as expired")
            return True
        except Exception as error:
            self.logger.error(f"[Auth] Failed to mark auth #{index} as expired: {error}")
            return False

    async def unmark_as_expired(self, index: int) -> bool:
        """
        Unmark an auth as expired (restore it to active status)
        - Removes "expired" field from the auth file (configs/auth/auth-{index}.json)
        - Rebuilds rotation indices to include the restored account
        """
        if index not in self.available_indices:
            self.logger.warning(f"[Auth] Cannot unmark non-existent auth #{index} as expired")
            return False

        if index not in self.expired_indices:
            self.logger.debug(f"[Auth] Auth #{index} is not marked as expired")
            return False

        auth_file_path = Path.cwd() / "configs" / "auth" / f"auth-{index}.json"

        try:
            file_content = await Path(auth_file_path).read_text(encoding="utf-8")
            auth_data = json.loads(file_content)
            if "expired" in auth_data:
                del auth_data["expired"]
            await Path(auth_file_path).write_text(json.dumps(auth_data, indent=2), encoding="utf-8")

            # Rebuild rotation indices to include this restored account
            self._build_rotation_indices()

            self.logger.info(f"[Auth] ✅ Restored auth #{index} from expired status")
            return True
        except Exception as error:
            self.logger.error(f"[Auth] Failed to unmark auth #{index} as expired: {error}")
            return False

    def get_rotation_indices(self) -> List[int]:
        return self.rotation_indices.copy()

    def get_duplicate_groups(self) -> List[Dict]:
        return self.duplicate_groups.copy()

    def get_canonical_index(self, index: int) -> Optional[int]:
        return self.canonical_index_map.get(index)

    def is_expired(self, index: int) -> bool:
        return index in self.expired_indices