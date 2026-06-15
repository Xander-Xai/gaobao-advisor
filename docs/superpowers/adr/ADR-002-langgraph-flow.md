# ADR-002: LangGraph for Conversation Workflow

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
Multi-turn conversation requires state management:
- Slot filling across turns
- Memory management (recent + summary)
- Conditional branching (RAG lookup → LLM → response)
- Emotion/coaching state transitions

Alternative: manual state machine (brittle, not extensible).

## Decision
Use LangGraph to define the conversation as a directed state graph.
Node types: InputValidation → SlotExtraction → RAGRetrieval → LLMReasoning → Response

## Consequences
+ Explicit state machine — easy to trace and debug
+ Built-in checkpointing and conversation memory
+ Modular nodes — each node is a testable unit
- Requires synchronous thread-pool execution (not native async)
- LangGraph dependency management complexity

## Related
- ADR-001: FastAPI migration (SSE integration)