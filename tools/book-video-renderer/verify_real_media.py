"""Audit a future real-video run without generating, uploading or synthesizing.

This verifies local provenance/QC, not a vendor bill or the authenticity of an
external service receipt. A request ID is recorded when the service exposes it.
"""
import argparse
import json
from pathlib import Path

from book_video_renderer.manifest import digest
from book_video_renderer.models import RenderError
from book_video_renderer.providers.video import validate_video_asset, FalH3MaxTurboVideoProvider
from book_video_renderer.qc import verify_video
from book_video_renderer.validator import load_storyboard


def verify(storyboard, output, images):
    storyboard, output, images = Path(storyboard), Path(output), Path(images)
    data = load_storyboard(storyboard)
    manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('overall_status') != 'completed' or not manifest.get('require_video_assets'):
        raise RenderError('Real-media audit requires a completed require-video-assets manifest')
    if manifest.get('storyboard_sha256') != digest(storyboard):
        raise RenderError('Storyboard hash does not match render input')
    expected_ids = [s['id'] for s in data['scenes']]
    if [e['id'] for e in manifest['scenes']] != expected_ids:
        raise RenderError('Manifest scene order/count differs from source')
    entries = {e['id']: e for e in manifest['scenes']}
    clips = []
    for scene in data['scenes']:
        if scene['visual']['type'] not in ('video', 'broll'):
            continue
        entry = entries[scene['id']]
        provenance = entry.get('video_provenance') or {}
        source = images/(scene['id']+'.png')
        if (entry.get('visual_source') != 'video' or entry.get('placeholder')
                or provenance.get('origin') != 'generated_video'
                or provenance.get('provider') != 'fal-minimax-h3-max-turbo'
                or not provenance.get('model') or not provenance.get('input_key')
                or provenance.get('source_image_sha256') != digest(source)):
            raise RenderError(f"{scene['id']}: missing/mismatched generated-video provenance")
        provider = FalH3MaxTurboVideoProvider(images, 1, require_api_key=False,
                                             clip_seconds=provenance['requested_duration_seconds'])
        if provenance['input_key'] != provider._input_key(scene, source):
            raise RenderError(f"{scene['id']}: input fingerprint mismatch")
        path = Path(entry['video_asset_path'])
        metadata = validate_video_asset(path)
        if not (digest(path) == entry['video_asset_sha256'] == provenance['sha256']):
            raise RenderError(f"{scene['id']}: clip SHA mismatch")
        scene_path = Path(entry['scene_video_path'])
        verify_video(scene_path, entry['duration'], entry['audio'])
        if digest(scene_path) != entry['sha256']:
            raise RenderError(f"{scene['id']}: encoded scene SHA mismatch")
        clips.append(dict(scene_id=scene['id'], source_image=str(source),
                          source_image_sha256=digest(source), provider=provenance['provider'],
                          model=provenance['model'], input_fingerprint=provenance['input_key'],
                          output_path=str(path), **{k: v for k, v in metadata.items() if k != 'path'},
                          cache_status=provenance['cache_status'],
                          estimated_cost_usd=provenance['estimated_cost_usd'],
                          confirmed_actual_cost_usd=provenance.get('confirmed_actual_cost_usd'),
                          service_request_id=provenance.get('request_id'), renderer_visual_source='video'))
    final = output/'final.mp4'
    if digest(final) != manifest['final_sha256']:
        raise RenderError('Final SHA mismatch')
    qc = verify_video(final, manifest['total_duration_seconds'], bool(manifest['qc']['audio_codec']))
    return dict(status='LOCAL_PROVENANCE_AND_QC_PASS', clips=clips, final_sha256=digest(final),
                qc=qc, scene_count=len(expected_ids),
                speech_status=manifest['speech_status'], subtitles=manifest['subtitles'],
                external_service_and_billing_evidence='requires independent service receipts; not established by this local audit')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storyboard', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-images', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.storyboard, args.output, args.source_images)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
