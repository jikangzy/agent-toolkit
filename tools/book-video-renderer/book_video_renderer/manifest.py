from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save_json(path: Path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def retry(action, attempts, on_failure):
    for attempt in range(1, attempts+1):
        try:
            return action()
        except Exception as exc:
            on_failure(attempt, str(exc))
            if attempt == attempts:
                raise
            time.sleep(min(.25 * 2**(attempt-1), 2))
