"""Where uploaded files live. Local disk now; an S3-compatible store implements the same API."""

import hashlib
import uuid
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def put(self, org_id: uuid.UUID, data: bytes) -> tuple[str, str]: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, org_id: uuid.UUID, data: bytes) -> tuple[str, str]:
        """Store content-addressed per organization. Returns (key, sha256)."""
        checksum = hashlib.sha256(data).hexdigest()
        key = f"{org_id}/{checksum}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return key, checksum

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key escapes the storage root")
        return path
