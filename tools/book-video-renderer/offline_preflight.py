"""Execute the actual Pipeline CLI with network and generation fail-closed guards."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    options, cli = parser.parse_known_args()
    if '--video-preflight-only' not in cli:
        parser.error('only --video-preflight-only execution is allowed')
    counters = dict(network_attempts_blocked=0, generation_api_attempts_blocked=0)

    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'http.client.connect'):
            counters['network_attempts_blocked'] += 1
            raise RuntimeError('Network prohibited during offline preflight')

    def prohibited(*args, **kwargs):
        counters['generation_api_attempts_blocked'] += 1
        raise RuntimeError('Generation/upload prohibited during offline preflight')

    sys.addaudithook(audit)
    # Stub only the forbidden external boundary; the CLI and preflight code are
    # real, and all source images/cache/budget calculations use actual inputs.
    module = types.ModuleType('fal_client')
    module.upload_file = module.subscribe = module.run = module.submit = prohibited
    sys.modules['fal_client'] = module
    os.environ.pop('FAL_KEY', None)
    sys.argv = [str(Path(__file__).with_name('pipeline.py')), *cli]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            runpy.run_path(sys.argv[0], run_name='__main__')
        except SystemExit as exc:
            code = exc.code or 0
    result = json.loads(stdout.getvalue()) if stdout.getvalue().strip() else {}
    result['execution_guard'] = dict(**counters, credentials_removed=True,
                                    network_requests_made=0, paid_requests_made=0,
                                    exit_code=code, stderr=stderr.getvalue(), cli_arguments=cli)
    options.report.parent.mkdir(parents=True, exist_ok=True)
    options.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if code or any(counters.values()):
        raise SystemExit(code or 1)


if __name__ == '__main__':
    main()
