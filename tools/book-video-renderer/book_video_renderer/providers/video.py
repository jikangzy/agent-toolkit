"""Video asset providers: local file ingestion and opt-in fal.ai image-to-video."""
from __future__ import annotations

import json
import math
import os
from fractions import Fraction
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image

from ..ffmpeg import probe, command
from ..manifest import digest, fingerprint, save_json
from ..models import RenderError
from .image import PlaceholderImage, find_visual_asset

VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".mkv", ".webm")
FAL_H3_MAX_TURBO_MODEL = "minimax/h3-max-turbo/image-to-video"
FAL_H3_MAX_TURBO_USD_PER_SECOND = 0.025
FAL_OUTPUT_DURATION_OVERHEAD_SECONDS = 0.7
VIDEO_PROVIDER_CACHE_VERSION = "video-provider-cache-v2"


class VideoProvider(Protocol):
    """Return a reusable local video file for a scene, or None if unavailable."""

    cache_key: str
    provider_name: str

    def get_or_generate_video(
        self, scene: dict, duration_seconds: float, workdir: Path
    ) -> Path | None: ...


def find_video_asset(assets_dir: Path | str | None, scene_id: str) -> Path | None:
    """Find exactly one pre-generated clip named after a scene ID."""
    if assets_dir is None:
        return None
    directory = Path(assets_dir).expanduser().resolve()
    matches = [directory / f"{scene_id}{extension}" for extension in VIDEO_EXTENSIONS
               if (directory / f"{scene_id}{extension}").is_file()]
    if len(matches) > 1:
        raise RenderError(
            f"{scene_id}: multiple video assets found; keep exactly one of "
            + ", ".join(VIDEO_EXTENSIONS)
        )
    return matches[0] if matches else None


def validate_video_asset(path: Path | str) -> dict:
    """Fail fast for unreadable files or assets without a real video stream."""
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise RenderError(f"Video asset does not exist or is empty: {path}")
    try:
        metadata = probe(path)
    except Exception as exc:
        raise RenderError(f"Cannot probe video asset {path}: {exc}") from exc
    stream = next((item for item in metadata.get("streams", [])
                   if item.get("codec_type") == "video"), None)
    if stream is None:
        raise RenderError(f"Video asset contains no video stream: {path}")
    try:
        duration = float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RenderError(f"Video asset has no valid duration: {path}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise RenderError(f"Video asset has invalid duration: {path}")
    try:
        fps = float(Fraction(stream.get('avg_frame_rate') or stream['r_frame_rate']))
        if (not stream.get('codec_name') or int(stream['width']) <= 0
                or int(stream['height']) <= 0 or not math.isfinite(fps) or fps <= 0):
            raise ValueError('invalid stream metadata')
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise RenderError(f"Video asset has invalid codec/dimensions/fps: {path}") from exc
    # ffprobe headers alone do not establish that every frame is readable.
    command(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', path,
             '-map', '0:v:0', '-f', 'null', '-'])
    return {"path": str(path), "duration_seconds": duration,
            "width": stream.get("width"), "height": stream.get("height"),
            "codec": stream.get("codec_name"), "fps": fps,
            "size_bytes": path.stat().st_size, "sha256": digest(path),
            "ffprobe_status": "PASS", "full_decode_status": "PASS"}


def download_video(url: str, destination: Path, max_bytes: int = 512 * 1024 * 1024) -> Path:
    """Download a generated clip safely to a temporary local file."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RenderError("Video provider returned a non-HTTPS download URL")
    request = Request(url, headers={"User-Agent": "agent-toolkit-book-video/1.0"})
    total = 0
    try:
        with urlopen(request, timeout=180) as response, Path(destination).open("wb") as output:
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and not (content_type.startswith("video/") or content_type == "application/octet-stream"):
                raise RenderError(f"Video provider returned unexpected content type: {content_type}")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RenderError("Generated video exceeded the 512 MiB download limit")
                output.write(chunk)
    except RenderError:
        Path(destination).unlink(missing_ok=True)
        raise
    except Exception as exc:
        Path(destination).unlink(missing_ok=True)
        raise RenderError(f"Could not download generated video: {exc}") from exc
    if total == 0:
        Path(destination).unlink(missing_ok=True)
        raise RenderError("Video provider returned an empty file")
    return Path(destination)


class SuppliedVideoProvider:
    """Resolve caller-supplied MP4/MOV/WebM clips without any network request."""

    cache_key = "supplied-video-v1"
    provider_name = "supplied-video"

    def __init__(self, assets_dir: Path | str):
        self.assets_dir = Path(assets_dir).expanduser().resolve()
        if not self.assets_dir.is_dir():
            raise RenderError(f"Video assets directory does not exist: {self.assets_dir}")

    def get_or_generate_video(self, scene, duration_seconds, workdir):
        asset = find_video_asset(self.assets_dir, scene["id"])
        if asset is not None:
            validate_video_asset(asset)
        return asset


class FalH3MaxTurboVideoProvider:
    """Paid image-to-video adapter. Calls fal only when explicitly selected.

    The adapter owns a per-scene cache and requires a caller-supplied USD budget.
    """

    provider_name = "fal-minimax-h3-max-turbo"
    model_id = FAL_H3_MAX_TURBO_MODEL
    cost_per_second_usd = FAL_H3_MAX_TURBO_USD_PER_SECOND

    def __init__(
        self,
        image_assets_dir: Path | str,
        budget_usd: float,
        clip_seconds: int = 5,
        resolution: str = "768P",
        require_api_key: bool = True,
    ):
        self.image_assets_dir = Path(image_assets_dir).expanduser().resolve()
        if not self.image_assets_dir.is_dir():
            raise RenderError(f"Image assets directory does not exist: {self.image_assets_dir}")
        if require_api_key and not os.environ.get("FAL_KEY"):
            raise RenderError("FAL_KEY is required for --ai-video-provider fal-h3-max-turbo")
        if budget_usd is None or not math.isfinite(budget_usd) or budget_usd <= 0:
            raise RenderError("fal video generation requires a positive --video-budget-usd cap")
        if clip_seconds not in (5, 10):
            raise RenderError("--video-clip-seconds must be 5 or 10")
        if resolution != "768P":
            raise RenderError("The initial fal adapter supports 768P generation only")
        self.budget_usd = float(budget_usd)
        self.clip_seconds = int(clip_seconds)
        self.resolution = resolution
        self.cache_key = f"fal:{self.model_id}:{self.resolution}:{self.clip_seconds}:v2"
        self.require_api_key = bool(require_api_key)
        self.preflight_report = {}
        self.scene_records = {}
        self._allowed_inputs = None
        self.runtime_statistics = {'uploads_attempted': 0, 'paid_request_attempts': 0,
                                   'downloads_attempted': 0, 'confirmed_actual_cost_usd': None}

    @property
    def estimated_clip_cost(self):
        return round((self.clip_seconds + FAL_OUTPUT_DURATION_OVERHEAD_SECONDS)
                     * self.cost_per_second_usd, 4)

    def _ledger(self, cache_root):
        path = Path(cache_root) / 'request-ledger.json'
        if not path.exists():
            return {'version': 1, 'attempts': []}
        try:
            ledger = json.loads(path.read_text(encoding='utf-8'))
            if ledger['version'] != 1 or not isinstance(ledger['attempts'], list):
                raise ValueError('unknown ledger format')
            for entry in ledger['attempts']:
                amount = entry['estimated_reserved_usd']
                if not math.isfinite(amount) or amount <= 0 or not entry['input_key']:
                    raise ValueError('invalid reservation')
            return ledger
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RenderError('Invalid request ledger; reconcile manually before any paid retry') from exc

    def _image(self, scene):
        image = find_visual_asset(self.image_assets_dir, scene["id"])
        if image is None:
            raise RenderError(
                f"{scene['id']}: fal image-to-video requires a still image in "
                f"{self.image_assets_dir}"
            )
        try:
            with Image.open(image) as source:
                source.verify()
            with Image.open(image) as source:
                source.load()
        except Exception as exc:
            raise RenderError(
                f"{scene['id']}: invalid source image for fal video generation: {image}: {exc}"
            ) from exc
        return image

    def _input_key(self, scene, image):
        return fingerprint({
            "cache_version": VIDEO_PROVIDER_CACHE_VERSION,
            "scene": {"id": scene["id"], "visual": scene["visual"]},
            "image_sha256": digest(image),
            "model": self.model_id,
            "resolution": self.resolution,
            "clip_seconds": self.clip_seconds,
            "prompt_policy": "storyboard-prompt-plus-motion-no-text-v1",
        })

    def _valid_cache(self, scene, image, workdir):
        video = workdir / "generated.mp4"
        metadata = workdir / "complete.json"
        input_key = self._input_key(scene, image)
        if not video.is_file() or not metadata.is_file():
            return None
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            if record.get("input_key") != input_key or record.get("sha256") != digest(video):
                return None
            if (record.get('provider') != self.provider_name or record.get('model') != self.model_id
                    or record.get('source_image_sha256') != digest(image)
                    or record.get('origin') != 'generated_video'):
                return None
            validate_video_asset(video)
            return video
        except (OSError, ValueError, KeyError, RenderError):
            return None

    def preflight(self, scenes, cache_root: Path | str):
        """Check inputs and estimated spend before the first paid API request."""
        cache_root = Path(cache_root).expanduser().resolve()
        eligible = [scene for scene in scenes if scene["visual"]["type"] in ("video", "broll")]
        if len({scene['id'] for scene in eligible}) != len(eligible):
            raise RenderError('Duplicate dynamic scene IDs')
        missing_images = [
            scene["id"] for scene in eligible
            if find_visual_asset(self.image_assets_dir, scene["id"]) is None
        ]
        if missing_images:
            raise RenderError(
                "fal image-to-video requires a still image for each video/broll scene: "
                + ", ".join(missing_images)
            )
        cached, billable = [], []
        for scene in eligible:
            image = self._image(scene)
            workdir = cache_root / scene["id"]
            if self._valid_cache(scene, image, workdir):
                cached.append(scene["id"])
            else:
                billable.append(scene["id"])
        ledger = self._ledger(cache_root)
        reserved = round(sum(a['estimated_reserved_usd'] for a in ledger['attempts']), 4)
        for scene in eligible:
            if scene['id'] in billable:
                key = self._input_key(scene, self._image(scene))
                if any(a['input_key'] == key for a in ledger['attempts']):
                    raise RenderError(f"{scene['id']}: prior request exists without valid cache; reconcile billing/result before retry")
        estimate = round(len(billable) * self.estimated_clip_cost, 4)
        if reserved + estimate > self.budget_usd + 1e-9:
            raise RenderError(
                f"Estimated fal video spend USD {reserved + estimate:.4f} for {len(billable)} uncached clips "
                f"exceeds video budget USD {self.budget_usd:.2f}; increase the explicit cap "
                "or reduce --video-clip-seconds."
            )
        self.preflight_report = {
            "provider": self.provider_name,
            "model": self.model_id,
            "resolution": self.resolution,
            "clip_seconds_requested": self.clip_seconds,
            "estimated_uncached_clips": len(billable),
            "cached_scene_ids": cached,
            "billable_scene_ids": billable,
            "estimated_cost_usd": estimate,
            "budget_usd": self.budget_usd,
            "estimated_cost_per_clip_usd": self.estimated_clip_cost,
            "estimated_prior_reserved_usd": reserved,
            "estimated_total_reserved_and_pending_usd": round(reserved + estimate, 4),
            "dynamic_scene_ids": [s['id'] for s in eligible],
            "network_requests_made": 0,
            "paid_requests_made": 0,
            "images_uploaded": 0,
            "generation_api_calls": 0,
            "budget_check": "PASS",
            "cost_basis_usd_per_second": self.cost_per_second_usd,
            "estimate_includes_duration_overhead_seconds_per_clip": FAL_OUTPUT_DURATION_OVERHEAD_SECONDS,
        }
        self._allowed_inputs = {s['id']: self._input_key(s, self._image(s)) for s in eligible}
        return self.preflight_report

    def get_or_generate_video(self, scene, duration_seconds, workdir):
        if scene["visual"]["type"] not in ("video", "broll"):
            return None
        image = self._image(scene)
        workdir = Path(workdir).expanduser().resolve()
        cached = self._valid_cache(scene, image, workdir)
        if cached is not None:
            record = json.loads((workdir / 'complete.json').read_text(encoding='utf-8'))
            self.scene_records[scene['id']] = {**record, 'cache_status': 'hit', 'output_path': str(cached)}
            return cached
        if not os.environ.get("FAL_KEY"):
            raise RenderError("FAL_KEY is required before paid fal video generation")
        key = self._input_key(scene, image)
        if self._allowed_inputs is None:
            self.preflight([scene], workdir.parent)
        if self._allowed_inputs.get(scene['id']) != key:
            raise RenderError(f"{scene['id']}: input/scope differs from preflight; rerun preflight")
        # Exclusive per-run lock + durable reservation precede any API operation.
        # Uncertain/failed attempts remain reserved across restarts. No auto retry.
        workdir.parent.mkdir(parents=True, exist_ok=True)
        lock = workdir.parent / 'request-ledger.lock'
        try:
            handle = lock.open('x', encoding='utf-8')
        except FileExistsError as exc:
            raise RenderError('Paid request ledger is locked; do not run concurrent generation') from exc
        try:
            return self._generate_locked(scene, image, key, workdir)
        finally:
            handle.close()
            lock.unlink(missing_ok=True)

    def _generate_locked(self, scene, image, key, workdir):
        ledger = self._ledger(workdir.parent)
        if any(a['input_key'] == key for a in ledger['attempts']):
            raise RenderError(f"{scene['id']}: prior request exists; reconcile before retry")
        spent = sum(a['estimated_reserved_usd'] for a in ledger['attempts'])
        if spent + self.estimated_clip_cost > self.budget_usd + 1e-9:
            raise RenderError('Paid request would exceed remaining video budget')
        workdir.mkdir(parents=True, exist_ok=True)
        temporary = workdir / "generated.partial.mp4"
        output = workdir / "generated.mp4"
        try:
            import fal_client
        except ImportError as exc:
            raise RenderError(
                "fal-client is not installed; run pip install -r "
                "tools/book-video-renderer/requirements-video-fal.txt"
            ) from exc

        attempt = {'scene_id': scene['id'], 'input_key': key,
                   'estimated_reserved_usd': self.estimated_clip_cost,
                   'status': 'reserved', 'paid_request_attempts': 0,
                   'confirmed_actual_cost_usd': None}
        ledger['attempts'].append(attempt)
        ledger_path = workdir.parent / 'request-ledger.json'
        save_json(ledger_path, ledger)

        visual = scene["visual"]
        motion = visual.get("motion", "")
        prompt = (
            f"{visual['prompt']}\n"
            f"Motion direction: {motion}. Preserve the subject and composition of the supplied first frame. "
            "Use natural continuous motion. Do not add text, captions, logos, or watermarks."
        )
        if visual.get('negative_prompt'):
            prompt += f"\nAvoid: {visual['negative_prompt']}"
        try:
            snapshot = workdir / ('source' + image.suffix.lower())
            payload = image.read_bytes()
            if self._input_key(scene, image) != key:
                raise RenderError('Source input changed before upload; reservation retained')
            snapshot.write_bytes(payload)
            if self._input_key(scene, snapshot) != key:
                raise RenderError('Source snapshot differs from preflight; reservation retained')
            self.runtime_statistics['uploads_attempted'] += 1
            image_url = fal_client.upload_file(str(snapshot))
            attempt.update(status='submitted_or_uncertain', paid_request_attempts=1)
            save_json(ledger_path, ledger)
            self.runtime_statistics['paid_request_attempts'] += 1
            result = fal_client.subscribe(
                self.model_id,
                arguments={
                    "prompt": prompt,
                    "image_url": image_url,
                    "duration": self.clip_seconds,
                    "resolution": self.resolution,
                    "prompt_expansion_mode": "disabled",
                    "enable_safety_checker": True,
                },
            )
        except Exception as exc:
            attempt['status'] = 'failed_or_uncertain'
            save_json(ledger_path, ledger)
            # External exception text may include credentials; never persist it.
            raise RenderError(
                f"{scene['id']}: fal video generation request failed ({type(exc).__name__}); reservation retained, no automatic retry"
            ) from None
        video_url = (result.get("video") or {}).get("url") if isinstance(result, dict) else None
        if not video_url:
            raise RenderError(f"{scene['id']}: fal response did not include video.url")
        self.runtime_statistics['downloads_attempted'] += 1
        download_video(video_url, temporary)
        metadata = validate_video_asset(temporary)
        temporary.replace(output)
        metadata['path'] = str(output)
        record = {
            "input_key": key,
            "sha256": digest(output),
            "provider": self.provider_name,
            "model": self.model_id,
            "origin": "generated_video",
            "source_image_path": str(image),
            "source_image_sha256": digest(snapshot),
            "confirmed_actual_cost_usd": None,
            "request_id": result.get('request_id'),
            "resolution": self.resolution,
            "requested_duration_seconds": self.clip_seconds,
            "estimated_cost_usd": round(
                (self.clip_seconds + FAL_OUTPUT_DURATION_OVERHEAD_SECONDS) * self.cost_per_second_usd, 4
            ),
            "video_metadata": metadata,
        }
        save_json(workdir / "complete.json", record)
        attempt['status'] = 'completed'
        save_json(ledger_path, ledger)
        self.scene_records[scene['id']] = {**record, 'cache_status': 'miss_generated', 'output_path': str(output)}
        return output


class StaticVideoFallback:
    """Legacy still-image fallback for storyboard scenes without a supplied clip."""

    cache_key = "static-video-v1"

    def generate_video(self, scene, font_path, output_path):
        return PlaceholderImage().generate_image(scene, font_path, output_path)
