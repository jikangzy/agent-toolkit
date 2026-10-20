# Agent Toolkit

A personal monorepo for reusable agent capabilities, including Skills, MCP servers, orchestration tools, shared schemas, and examples.

## Repository layout

```text
agent-toolkit/
├── skills/       # Reusable agent Skills
├── mcps/         # MCP servers and integrations
├── tools/        # Standalone agent/orchestration tools
├── schemas/      # Shared machine-readable contracts
├── examples/     # End-to-end examples and fixtures
├── scripts/      # Local setup / install helpers
└── docs/         # Architecture and development notes
```

## Current capabilities

### Book Video

The first experiment separates creative planning from deterministic media production:

```text
Book title
   ↓
WorkBuddy / book-story-producer
   ↓
storyboard.json
   ↓
Codex / book-video-renderer
   ↓
final.mp4
```

- `skills/book-video/story-producer/`: creates a fact-grounded Chinese short-video storyboard from a book title.
- `skills/book-video/video-renderer/`: consumes a locked storyboard, uses optional agent-generated still images, optional Chinese TTS, subtitles, and FFmpeg to produce the final video.
- `tools/book-video-renderer/`: deterministic renderer CLI. Pass `--assets-dir output/<run-id>/images` with files named `scene_001.png`, etc.; it normalizes images to 1080×1920, overlays the storyboard's exact on-screen text, and records per-scene asset hashes for caching.
- `schemas/book-video/storyboard.schema.json`: contract between the two stages.
- `examples/book-video/storyboard.example.json`: sample payload for testing.

**Current MVP limitations:** image generation happens in the agent workflow, not inside the CLI; missing images become clearly labeled placeholders. Edge TTS is optional and online (narration text is sent to the external service); the default renderer has no narration. Local background music can be mixed using `--music-file`, but music generation is not implemented. The TTS preflight can create word-boundary-timed subtitles when the provider metadata exactly matches the original narration, with a safe scene-timing fallback otherwise. AI video generation and guaranteed word-level subtitle alignment across all providers are not implemented. See [Book Video Renderer documentation](tools/book-video-renderer/README.md) for commands and validation details.

Run the offline MVP from the repository root (FFmpeg/ffprobe and a CJK font required):

```bash
python -m pip install -r tools/book-video-renderer/requirements.txt
python tools/book-video-renderer/renderer.py render \
  --storyboard examples/book-video/naval-test-001/storyboard.json \
  --output output/naval-test-001
```

This preserves the storyboard, creates per-scene MP4s, burns Chinese subtitles,
verifies the final video, and records cache/fallback/QC details in `manifest.json`.
No API key or external service is needed. The default has placeholder visuals and
no speech audio or BGM. Repeating the command reuses validated scene caches. See
[renderer documentation](tools/book-video-renderer/README.md) for provider interfaces,
font failure recovery, tests, and manifest fields.

## Install WorkBuddy skills

On Windows, run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-workbuddy-skills.ps1
```

By default the script installs the skills to the current user's WorkBuddy / CodeBuddy skill directory:

```text
%USERPROFILE%\.codebuddy\skills\
├── book-story-producer\
└── book-video-renderer\
```

To install project-local copies instead:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-workbuddy-skills.ps1 -Scope project
```

## Generated data policy

Generated media is **local by default** and should not be committed to Git.

Keep locally:
- rendered videos
- generated images / video clips
- TTS audio
- subtitles created for a run
- temporary files and provider caches
- per-run manifests that contain machine-specific paths or provider responses

Recommended local paths:

```text
output/
.local/runs/
runs/
artifacts/
cache/
```

Commit only durable source-of-truth material:
- Skills
- schemas
- scripts
- provider adapters
- hand-curated prompts/configuration
- deliberately selected example storyboards and small fixtures

If a generated final video needs to be shared, prefer GitHub Releases or object storage over committing large binaries to the repository.

## Reserved tool space

`tools/` is reserved for standalone runtimes, CLIs, orchestrators, and local services. A future OpenSpec-related tool can live under a path such as:

```text
tools/openspec-agent-orchestrator/
```

No OpenSpec migration is part of the current Book Video experiment.

## Conventions

- Skills own agent behavior and prompt-level workflows.
- MCPs expose reusable external capabilities through MCP protocol.
- Tools are standalone runtimes, CLIs, orchestrators, or local services.
- Schemas define contracts shared across agents/tools.
- Examples should be runnable or directly usable as fixtures.
- Provider-specific media APIs should sit behind adapters so workflows remain vendor-neutral.
