from __future__ import annotations

import json
import subprocess
from .models import RenderError

def command(args, timeout=900):
    try:
        result = subprocess.run([str(a) for a in args], capture_output=True,
                                encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RenderError(str(exc)) from exc
    if result.returncode:
        raise RenderError(f'{args[0]} exited {result.returncode}: {result.stderr[-4000:]}')
    return result.stdout


def probe(path):
    return json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))
