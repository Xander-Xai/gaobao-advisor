# ADR-005: DashScope Voice Pipeline (ASR → Graph → TTS)

**Status:** Accepted (partially implemented)
**Date:** 2026-06

## Context
Phone-like voice interaction requires:
1. ASR (Automatic Speech Recognition) — convert user speech to text
2. Graph reasoning — run the conversation graph on transcribed text
3. TTS (Text-to-Speech) — convert response to speech
4. Voice rendering — adapt written response to spoken format

## Decision
Use Alibaba DashScope API for both ASR and TTS.
Route: ASR endpoint → LangGraph → Voice Render Prompt → TTS endpoint.

## Consequences
+ Single-provider simplicity (DashScope handles both ASR and TTS)
+ Voice render prompt adapts written response to spoken format (shorter sentences, no markdown)
- External API dependency — latency and cost per voice interaction
- TTS voice selection limited to DashScope voices