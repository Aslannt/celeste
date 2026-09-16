# Sandboxed environment for code_task (see docs/CODE_TASK.md and ADR-011).
#
# Nothing about this container is trusted with anything beyond the one
# repository directory Core mounts into it at run time (-v <repo>:/workspace).
# It never sees the rest of the host filesystem, Celeste's secrets, or
# CelesteBrain. Authentication is passed in per-run via CLAUDE_CODE_OAUTH_TOKEN
# (generated once on the host with `claude setup-token`), never baked into the
# image.

FROM node:20-slim

RUN npm install -g @anthropic-ai/claude-code

WORKDIR /workspace

ENTRYPOINT ["claude"]
