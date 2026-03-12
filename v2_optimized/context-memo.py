#!/usr/bin/env python3
"""
Context Memo - Inter-module state sharing for sequential pipeline.

JSON file-based memo enabling module1/2/3 to share state.
File stored at cache/context_memo.json.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional


class ContextMemo:
    """JSON file-based context sharing between pipeline modules."""

    def __init__(self, memo_path: str = None):
        if memo_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            memo_path = os.path.join(base_dir, "cache", "context_memo.json")
        self.memo_path = memo_path

    def save(self, stage: str, data: Dict[str, Any]) -> None:
        """Save stage output to memo. Merges with existing data."""
        try:
            memo = self._load()
            memo[stage] = data
            memo["updated_at"] = datetime.now().isoformat()
            self._write(memo)
        except Exception as e:
            print(f"[WARN] ContextMemo.save({stage}) failed: {e}")

    def read(self, stage: str = None) -> Optional[Dict[str, Any]]:
        """Read specific stage or full memo. Returns None if unavailable."""
        try:
            memo = self._load()
            if stage:
                return memo.get(stage)
            return memo
        except Exception:
            return None

    def clear(self) -> None:
        """Reset memo at pipeline start."""
        try:
            self._write({"created_at": datetime.now().isoformat()})
        except Exception as e:
            print(f"[WARN] ContextMemo.clear() failed: {e}")

    def _load(self) -> Dict[str, Any]:
        """Load memo from JSON file."""
        try:
            if os.path.exists(self.memo_path):
                with open(self.memo_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _write(self, data: Dict[str, Any]) -> None:
        """Atomic write using tempfile + rename."""
        os.makedirs(os.path.dirname(self.memo_path), exist_ok=True)
        dir_name = os.path.dirname(self.memo_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp_path, self.memo_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
