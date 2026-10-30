# Design

The Python pipeline owns validation, scene selection, audio, manifest, cache and FFmpeg QC. A HyperFrames provider generates a deterministic, self-contained composition for each scene and invokes a pinned local CLI. Scene cache keys cover storyboard content, source media, implementation and runtime versions. Final assembly applies the requested transition without changing the total frame count. No source storyboard is rewritten. Optional supplied narration is preserved; absent speech is explicitly reported, not synthesized. The fal provider remains available.

Visual direction follows the supplied storyboard: warm, quiet photographic study for scene 002 and deep blue contemplative imagery for scene 003, with restrained ivory typography and motion. Preserve the exact supplied text.
