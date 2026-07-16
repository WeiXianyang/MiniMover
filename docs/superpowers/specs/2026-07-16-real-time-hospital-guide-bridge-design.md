# Real-time Hospital Guide Bridge Design

**Date:** 2026-07-16

## Goal
Connect the Jetson car's existing WebSocket ASR `final_text` messages to the hospital-guide orchestrator, existing on-car TTS, real retrieval knowledge, and confirmation-gated navigation. The dashboard must display the actual session written by the running bridge, not replayed or fabricated events.

## Selected design
- Retain the existing PC-side ASR/wake-word transport and its Jetson `car_client.py` microphone process.
- Add a local Flask API `POST /api/hospital-guide/turn` that processes only finalized ASR text.
- Construct one stateful `HospitalGuideOrchestrator` at API startup. It owns multi-turn memory, reads the ShortMedKG JSONL corpus, calls the configured OpenAI-compatible LLM, and writes runtime telemetry.
- Make `car_client.py` call that local API only after receiving `final_text`; its reply is played through the existing `/api/audio/say` TTS endpoint.
- When `MINIMOVER_HOSPITAL_GUIDE_MODE=1`, ignore the legacy upstream `chat_reply` and `command` messages. This prevents duplicate speech and prevents the upstream command path from bypassing the guide's confirmation gate.
- Navigation remains disabled in the supplied department template. A target can only be enabled after its coordinates have been selected from the existing map page; confirmation still remains mandatory.

## Safety rules
- No endpoint in the dashboard sends navigation requests.
- The bridge endpoint accepts a short plain-text utterance only; it does not accept coordinates or department configuration changes.
- The only navigation client is owned by `HospitalGuideOrchestrator`; it is invoked only after a pending department and a confirmation phrase.
- Emergency language cancels a pending goal and advises immediate on-site emergency care.
- A knowledge-only fallback is used if the configured LLM is unavailable; it quotes a retrieved corpus snippet without diagnosis or prescribing.

## Deployment compatibility
The Jetson's `voice_assistant/car_client.py` is a WebSocket microphone client, unlike the local development `CarClient` HTTP class. The deployment therefore adds a small HTTP guide client rather than copying or replacing the existing client abstraction. Existing remote user changes in `api_server.py` and voice files are preserved with per-file backups and minimal patches.

## Known operational prerequisite
The Jetson's `maps/` directory currently contains only `.gitkeep`; its department template has navigation disabled. The real conversation and retrieval/TTS demonstration can run immediately. Before a physical navigation demonstration, an operator must start the existing navigation stack and select audited department points in the map UI, then enable only those corresponding template entries.
