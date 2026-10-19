---
name: book-story-producer
description: 从书名研究并生成约两分钟中文读书分享视频 storyboard.json；用于 Book Video 创作规划阶段。
allowed-tools: Read, Write, Bash, WebFetch, WebSearch
---

# book-story-producer

## Purpose
Given a book title, produce a fact-grounded Chinese short-video storyboard. The output is `storyboard.json` only.

## Input
- book title
- optional target duration; default 120 seconds
- optional style; default 知识类短视频
- optional aspect ratio; default 9:16

## Workflow
1. Identify the book and author. Resolve ambiguity before writing content when possible.
2. Research trustworthy summaries/reviews/official publisher information. Do not fabricate quotes.
3. Extract 2-4 core ideas suitable for a short book-sharing video.
4. Write a Chinese narration for approximately the requested duration.
5. Split the narration into 8-12 scenes for a 120-second video.
6. For each scene, specify the visual type and a concrete generation prompt.
7. Validate total scene duration against the target; tolerate +/- 8%.
8. Output valid JSON matching `schemas/book-video/storyboard.schema.json`.

## Content rules
- Never invent verbatim quotes from the book. If uncertain, paraphrase.
- Prefer one clear thesis over a chapter-by-chapter summary.
- Hook in the first 8 seconds.
- Keep language conversational and natural for voiceover.
- Each scene should communicate one visual idea.
- Prompts should describe visible composition, subject, setting, mood, camera language, and motion where relevant.
- Treat each `visual.prompt` as instructions for **one standalone still frame**, not a storyboard, collage, contact sheet, or poster.
- Use a consistent visual art direction across all scenes (palette, lighting, realism/illustration style, and lens language) so separate images feel like one video.
- Prefer a vertical 9:16 composition with the main subject away from the extreme edges and a clean lower area for subtitles.
- Do not ask image models to render titles, subtitles, labels, logos, watermarks, or readable book-cover text. The renderer overlays the exact `onscreen_text` from the storyboard.
- Describe only visual content that should be visible in the generated image; keep camera motion in the separate `visual.motion` field because the renderer animates still images with pan/zoom.
- Keep `negative_prompt` explicit about text, logos, watermarks, malformed hands/faces, clutter, and any unwanted style when relevant.
- Do not include provider-specific syntax.

## Output contract
Return only the JSON object. Do not wrap it in markdown fences.
