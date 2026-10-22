"""Validate checked-in Naval originals and derive a content-preserving fixture.

Remote verification requires a freshly fetched Git ref and (optionally) the
GitHub API recursive tree JSON saved for that exact ref. No generation API runs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = Path("examples/book-video/naval-test-001")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def validate(remote_ref="origin/main", remote_tree=None):
    from book_video_renderer.providers.image import find_visual_asset
    from book_video_renderer.validator import load_storyboard

    main_sha = git("rev-parse", remote_ref).decode().strip()
    tree_sha = git("rev-parse", f"{main_sha}^{{tree}}").decode().strip()
    tree = json.loads(Path(remote_tree).read_text(encoding="utf-8-sig")) if remote_tree else None
    if tree:
        assert tree["sha"] == tree_sha and not tree.get("truncated")
        entries = {item["path"]: item for item in tree["tree"]}
    source = ROOT / EXAMPLE / "storyboard.json"
    before = source.read_bytes()
    data = load_storyboard(source)
    remote_source = git("show", f"{main_sha}:{EXAMPLE.as_posix()}/storyboard.json")
    # Git text checkout may use CRLF on Windows. Compare all JSON fields as well
    # as record both byte hashes; the local source is never rewritten.
    assert data == json.loads(remote_source)
    expected = [f"scene_{n:03}" for n in range(2, 10)]
    assert [s["id"] for s in data["scenes"]] == [f"scene_{n:03}" for n in range(1, 11)]
    assert data["scenes"][0]["visual"]["type"] == data["scenes"][-1]["visual"]["type"] == "title_card"
    assert [s["id"] for s in data["scenes"] if s["visual"]["type"] in ("video", "broll")] == expected
    images = []
    for scene_id in expected:
        rel = EXAMPLE / "source-images" / f"{scene_id}.png"
        path = ROOT / rel
        payload = path.read_bytes()
        assert payload and payload.startswith(b"\x89PNG\r\n\x1a\n")
        blob = git("rev-parse", f"{main_sha}:{rel.as_posix()}").decode().strip()
        assert git("cat-file", "blob", blob) == payload
        if tree:
            assert entries[rel.as_posix()]["sha"] == blob
            assert entries[rel.as_posix()]["size"] == len(payload)
        with Image.open(io.BytesIO(payload)) as image:
            assert image.format == "PNG"
            image.verify()
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            width, height = image.size
            mode = image.mode
        assert height > width and abs(width / height - 9 / 16) < .01
        assert find_visual_asset(path.parent, scene_id) == path.resolve()
        images.append(dict(scene_id=scene_id, path=rel.as_posix(), width=width,
                           height=height, format="PNG", mode=mode, size_bytes=len(payload),
                           sha256=hashlib.sha256(payload).hexdigest(), decode_status="PASS",
                           portrait=True, aspect_ratio=f"{width}:{height}",
                           renderer_format_accepted=True, remote_main_verified=True,
                           remote_blob_sha=blob))
    fixture = copy.deepcopy(data)
    fixture["scenes"] = fixture["scenes"][1:3]
    fixture["format"]["target_duration_seconds"] = sum(s["duration_seconds"] for s in fixture["scenes"])
    assert fixture["scenes"] == data["scenes"][1:3]
    assert source.read_bytes() == before
    report = dict(status="PASS", remote_main_sha=main_sha, remote_tree_sha=tree_sha,
                  remote_verification_method="freshly fetched Git blobs, plus pinned GitHub API tree" if tree else "fetched Git ref and blob bytes",
                  image_count=len(images), images=images)
    integrity = dict(source_path=source.relative_to(ROOT).as_posix(),
                     original_storyboard_sha256=hashlib.sha256(before).hexdigest(),
                     remote_git_content_sha256=hashlib.sha256(remote_source).hexdigest(),
                     local_newline_note="raw local SHA may differ from Git LF blob due to CRLF checkout",
                     remote_json_equal=True, source_bytes_unchanged=True,
                     narration_unchanged=True, onscreen_text_unchanged=True, order_unchanged=True,
                     scene_count=10, dynamic_scene_ids=expected,
                     duration_seconds=sum(s["duration_seconds"] for s in data["scenes"]),
                     derived_scene_ids=[s["id"] for s in fixture["scenes"]],
                     derived_duration=fixture["format"]["target_duration_seconds"])
    return report, integrity, fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote-ref", default="origin/main")
    parser.add_argument("--remote-tree", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / EXAMPLE / "validation")
    args = parser.parse_args()
    report, integrity, fixture = validate(args.remote_ref, args.remote_tree)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("source-images-report.json", report), ("storyboard-integrity.json", integrity),
                        ("two-scene-storyboard.json", fixture)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_images": report["status"], "count": report["image_count"], **integrity}, indent=2))


if __name__ == "__main__":
    main()
