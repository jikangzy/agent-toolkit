# Architecture

## Capability boundaries

The monorepo intentionally distinguishes four layers:

- **Skill**: reasoning/workflow instructions used by an agent.
- **MCP**: reusable protocol-based capabilities exposed to agents.
- **Tool**: executable runtime, CLI, orchestrator, or service.
- **Schema**: stable contract connecting otherwise independent components.

## Book video example

```text
WorkBuddy (creative layer)
        |
        | storyboard.schema.json
        v
Codex (execution layer)
        |
        +--> image/video provider adapters
        +--> TTS provider adapter
        +--> subtitle generation/alignment
        +--> FFmpeg
        v
     final.mp4
```

The central design rule is that creative decisions are captured in a versioned contract before execution starts. This makes providers replaceable, failures resumable, and output reproducible.
