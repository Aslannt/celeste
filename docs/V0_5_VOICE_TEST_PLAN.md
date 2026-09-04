# V0.5 voice validation plan

Checklist for the Speech-to-Text/Text-to-Speech slice of V0.5 (branch `feat/voice-stt-tts-v0.5`, PR #12). Written the night this was built, with no phone connected - everything below that needs a real device is unchecked on purpose.

## Automated / no device needed

- [x] `compileDebugKotlin` succeeds.
- [x] `assembleDebug` produces `celeste-android/app/build/outputs/apk/debug/app-debug.apk`.
- [x] `celeste-core` test suite still green (`82 passed`) after the `.env` model change.
- [x] GitHub Actions `Celeste CI` green on `feat/voice-stt-tts-v0.5` (push and PR runs).
- [x] Merged `AndroidManifest.xml` confirmed to contain `RECORD_AUDIO` and the `<queries>` block for `android.speech.RecognitionService` (Android 11+ package-visibility rule).
- [x] `celeste-core` backend confirmed reachable and responding through the real assistant chat endpoint (see below), independent of the Android app.

## Backend sanity (done tonight, from curl, PC-only)

- [x] `GET /api/v1/status` -> `online`, `version 0.4.2`.
- [x] `POST /api/v1/assistant/chat` with a fast-path question (`Cual es el estado del PC?`) -> `provider: core_fast_path`, ~140ms round trip.
- [x] `POST /api/v1/assistant/chat` with a real conversational question -> `provider: ollama`, `model: qwen3.5:4b`.
  - Cold call (model not yet loaded): ~9.5s total (`load_ms` ~6.9s of that).
  - Warm call right after: ~2.7s total (`load_ms` ~3ms). This is the number that matters for how voice will actually feel - keep this warm-latency figure in mind, not the cold one.

## Android - needs the real phone (tomorrow)

- [ ] Install `app-debug.apk` on the phone (`adb install` or copy + open).
- [ ] Tap the mic button for the first time -> Android should show the runtime permission dialog for `RECORD_AUDIO`.
- [ ] Deny the permission once -> confirm the app shows the "necesita permiso de microfono" message instead of crashing, and the mic button still works if tapped again and granted.
- [ ] Grant the permission -> confirm the system speech-recognition UI opens (small mic overlay, usually Google's).
- [ ] Say a short Spanish phrase (e.g. "que tengo hoy en el calendario") -> confirm it is transcribed reasonably, appears in the input field, and is sent to Celeste automatically without an extra tap.
- [ ] Say something with no clear intent -> confirm Celeste still replies instead of erroring out.
- [ ] Confirm the reply is read aloud automatically in Spanish through TTS.
- [ ] Toggle "Leer respuestas en voz alta" off -> confirm the next reply is silent, and the reply is still shown as text.
- [ ] Toggle it back on -> confirm speech resumes.
- [ ] Try on a flaky/offline connection (or with Core temporarily stopped on the PC) -> confirm the app fails gracefully (no crash) and does not try to speak an empty/error reply oddly.
- [ ] Try with the phone's system language set to Spanish - since `EXTRA_LANGUAGE` is hardcoded to `es-CO`, this should work regardless of system language, but worth double-checking once for real.
- [ ] Note the actual perceived voice-to-voice latency (time from finishing speaking to hearing Celeste's answer start) on the real phone/network - the PC-side number above is only half the picture.

## Known gaps, not attempted tonight

- Driving mode, Bluetooth intercom pairing, and activation from the intercom button are unstarted (rest of V0.5 in `docs/ROADMAP.md`).
- No fallback if the device has no speech-recognition service installed at all (rare on real phones with Google apps, but the code path exists and shows a message instead of crashing - worth confirming once).
- "Leer respuestas en voz alta" is in-memory only; it resets to on every app restart. Fine as a default, but not persisted through `ConfigStore` yet.
