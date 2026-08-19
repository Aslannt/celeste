# V0.4 validation plan

This checklist keeps the AI/Tool Router increment testable before it is merged into `main`.

## Automated

- [x] GitHub Actions: Core test job passes on the pre-Ollama V0.4 head.
- [x] GitHub Actions: Android debug build passes on the pre-Ollama V0.4 head.
- [x] Windows: `celeste-core/test_windows.ps1` passes after pulling the latest pre-Ollama branch (`18 passed`).
- [ ] Re-run CI and Windows tests after the Ollama provider commits.

## Core on the real PC

- [x] `/api/v1/status` reports `0.4.0` on the real Windows PC.
- [x] `search_memory` executes as `READ` on the real Brain.
- [x] `create_note` executes as `SAFE_WRITE` and writes/indexes a real Markdown note.
- [x] `get_pc_status` executes as `READ`.
- [x] Repeat the Core suite after the confirmation/audit hardening commits (`18 passed`).
- [ ] Confirm `/api/v1/assistant/audit` records tool outcomes without note contents.
- [ ] Test a real `delete_note` request with a conversational provider: verify it remains pending until explicit confirmation.
- [ ] Verify cancel leaves the note untouched.
- [ ] Verify confirm performs a soft delete (`deleted=true`) and removes it from FTS results.

## Android

- [x] Build/install Android `0.4.0` after the latest confirmation UI changes.
- [x] Ask Celeste to search memory.
- [x] Ask Celeste to create a memory.
- [ ] Verify pending `CONFIRM` actions show Confirm/Cancel buttons with a real conversational provider.
- [ ] Confirm and cancel sample actions from the phone.

## Ollama provider

- [x] Install Ollama on the real Windows PC.
- [x] Pull and run `qwen3.5:9b` locally.
- [x] Verify `ollama ps` reports the model running with GPU acceleration.
- [ ] Pull the latest V0.4 branch containing `OllamaProvider`.
- [ ] Set `CELESTE_LLM_PROVIDER=ollama`, `CELESTE_LLM_MODEL=qwen3.5:9b` and local Ollama URL.
- [ ] Verify a normal conversation reports `provider=ollama`.
- [ ] Test natural-language routing to `search_memory`, `create_note` and `get_pc_status`.
- [ ] Verify `update_note` and `delete_note` remain pending until explicit confirmation.
- [ ] Verify Cancel and Confirm from Android.

The native Ollama `/api/chat` integration uses tool calling through Celeste's existing Tool Router. `CELESTE_OLLAMA_THINK=false` is the default so simple assistant requests do not expose or spend time generating an unnecessary reasoning trace. No Ollama API key is required for the default localhost endpoint.

## OpenAI provider (optional)

- [ ] Configure a private `OPENAI_API_KEY` locally; never commit it.
- [ ] Set `CELESTE_LLM_PROVIDER=openai`.
- [ ] Test natural-language routing to `search_memory`, `create_note` and `get_pc_status`.
- [ ] Verify destructive note mutations require confirmation.
- [ ] Keep `store=false` and `parallel_tool_calls=false` in provider requests.

OpenAI is optional; V0.4 is allowed to use Ollama as the primary conversational provider once the same Tool Router and confirmation guarantees pass real-device validation.

Do not merge this PR merely because automated CI is green. The explicit confirmation UX should still be tested on the real phone before merge.
