"""Local structural/evidence checks for this repository's OpenSpec Change.

This is not the upstream OpenSpec CLI (not configured in this repository).
"""
import json
from pathlib import Path

from book_video_renderer.providers.video import (
    FAL_H3_MAX_TURBO_USD_PER_SECOND, FAL_OUTPUT_DURATION_OVERHEAD_SECONDS,
)

ROOT = Path(__file__).resolve().parents[2]


def main():
    change = ROOT/'openspec/changes/real-media-e2e-validation'
    for name in ('proposal.md', 'tasks.md', 'specs/book-video-renderer/spec.md', 'CODEX_RUNBOOK.md', 'RUN_REPORT.md'):
        assert (change/name).read_text(encoding='utf-8').strip(), name
    spec = (change/'specs/book-video-renderer/spec.md').read_text(encoding='utf-8')
    assert spec.count('## Requirement:') >= 8 and spec.count('### Scenario:') >= 10
    tasks = (change/'tasks.md').read_text(encoding='utf-8')
    assert '- [x]' not in tasks.split('## Real-service acceptance')[1], 'Real-service tasks need independent paid evidence before checking them off'
    validation = ROOT/'examples/book-video/naval-test-001/validation'
    for label, count, cap in (('eight', 8, 1.20), ('two', 2, .40)):
        report = json.loads((validation/f'{label}-scene-preflight.json').read_text(encoding='utf-8'))
        result = report['video_preflight']
        guard = report['execution_guard']
        assert report['status'] == 'preflight_passed'
        assert result['dynamic_scene_ids'] == [f'scene_{i:03}' for i in range(2, 2+count)]
        assert result['estimated_uncached_clips'] == len(result['billable_scene_ids'])
        assert set(result['cached_scene_ids']).isdisjoint(result['billable_scene_ids'])
        cost = round(len(result['billable_scene_ids']) * (5+FAL_OUTPUT_DURATION_OVERHEAD_SECONDS) * FAL_H3_MAX_TURBO_USD_PER_SECOND, 4)
        assert result['estimated_cost_usd'] == cost and cost <= cap
        assert result['network_requests_made'] == result['paid_requests_made'] == result['images_uploaded'] == 0
        assert guard['network_attempts_blocked'] == guard['generation_api_attempts_blocked'] == guard['exit_code'] == 0
    print('PASS: OpenSpec structure, paid-task boundary, formal preflight scope/cost/guards')


if __name__ == '__main__':
    main()
