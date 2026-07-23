"""Ecriture JSON atomique safe sous concurrence (threads / process)."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    """Ecrit `payload` dans `path` via un fichier temporaire unique + rename.

    Evite FileNotFoundError quand plusieurs threads ecrivent le meme `.tmp` fixe.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if compact
        else json.dumps(payload, ensure_ascii=False, indent=2)
    )
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            tmp_path.write_text(text, encoding="utf-8")
            os.replace(tmp_path, path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.02 * (attempt + 1))
            try:
                if tmp_path.is_file():
                    tmp_path.unlink()
            except OSError:
                pass
            tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    if last_error is not None:
        raise last_error
