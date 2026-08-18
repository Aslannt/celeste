# V0.4 validation plan

This checklist keeps the AI/Tool Router increment testable before it is merged into `main`.

## Automated

- [ ] GitHub Actions: Core test job passes.
- [ ] GitHub Actions: Android debug build passes.
- [ ] Windows: `celeste-core/test_windows.ps1` passes after pulling the latest branch.

## Core on the real PC

- [x] `/api/v1/status` reports `0.4.0` on the real Windows PC (validated before the latest hardening commits).
- [x] `search_memory` executes as `READ` on the real Brain.
- [x] `create_note` executes as `SAFE_WRITE` and writes/indexes a real Markdown note.
- [x] `get_pc_status` executes as `READ`.
- [ ] Repeat the Core suite after the confirmation/audit hardening commits.
- [ ] Confirm `/api/v1/assistant/audit` records tool outcomes without note contents.
- [ ] Test a real `delete_note` request with an OpenAI provider: verify it remains pending until explicit confirmation.
- [ ] Verify cancel leaves the note untouched.
- [ ] Verify confirm performs a soft delete (`deleted=true`) and removes it from FTS results.

## Android

- [ ] Build/install Android `0.4.0` after the latest confirmation UI changes.
- [ ] Ask Celeste to search memory.
- [ ] Ask Celeste to create a memory.
- [ ] Verify pending `CONFIRM` actions show Confirm/Cancel buttons.
- [ ] Confirm and cancel sample actions from the phone.

## OpenAI provider

- [ ] Configure a private `OPENAI_API_KEY` locally; never commit it.
- [ ] Set `CELESTE_LLM_PROVIDER=openai`.
- [ ] Test natural-language routing to `search_memory`, `create_note` and `get_pc_status`.
- [ ] Verify destructive note mutations require confirmation.
- [ ] Keep `store=false` and `parallel_tool_calls=false` in provider requests.

Do not merge this PR merely because automated CI is green. The explicit confirmation UX should still be tested on the real phone before merge.
