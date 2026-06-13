"""Voice WebSocket endpoint — real-time voice interaction."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.graph.graph import get_advisor_graph
from server.services.voice import get_voice_service

router = APIRouter(tags=["voice"])


@router.websocket("/ws/call")
async def voice_call(
    websocket: WebSocket,
    session_id: str = "default",
    scene: str = "gaokao",
) -> None:
    """Real-time voice call endpoint.

    Protocol:
    - Client sends: {"type": "asr_result", "text": "..."} for transcribed text
    - Client sends: binary PCM frames for audio
    - Server sends: {"type": "user_text", "text": "..."} when user text received
    - Server sends: {"type": "assistant_text", "text": "..."} for assistant reply
    - Server sends: {"type": "tts_start"} / {"type": "tts_end"} for TTS lifecycle
    """
    await websocket.accept()
    voice_service = get_voice_service()
    graph = get_advisor_graph()
    session_messages: list[dict[str, str]] = []

    try:
        while True:
            data = await websocket.receive()

            if data["type"] == "websocket.receive" and isinstance(
                data.get("text"), str
            ):
                msg = json.loads(data["text"])

                if msg.get("type") == "asr_result" and msg.get("text"):
                    user_text = msg["text"]
                    await websocket.send_json(
                        {"type": "user_text", "text": user_text}
                    )

                    # Run planning graph
                    await websocket.send_json(
                        {"type": "assistant_text", "text": "正在分析..."}
                    )
                    result = await asyncio.to_thread(
                        graph.invoke,
                        {
                            "session_id": session_id,
                            "input_text": user_text,
                            "scene": scene,
                            "slots": {},
                            "messages": session_messages[-12:],
                            "trace": [],
                        },
                    )

                    reply = result.get("reply", "抱歉，暂时无法回答。")
                    session_messages.append(
                        {"role": "user", "content": user_text}
                    )
                    session_messages.append(
                        {"role": "assistant", "content": reply}
                    )

                    # Voice rendering
                    oral_reply = await voice_service.render_voice_reply(
                        reply, scene
                    )
                    await websocket.send_json(
                        {"type": "assistant_text", "text": oral_reply}
                    )

                    # TTS placeholder — full DashScope TTS streaming to be added
                    await websocket.send_json({"type": "tts_start"})
                    # In production: stream TTS audio frames via DashScope
                    await websocket.send_json({"type": "tts_end"})

            elif data["type"] == "websocket.receive" and isinstance(
                data.get("bytes"), bytes
            ):
                # Binary audio frames — passthrough to ASR when integrated
                pass

    except WebSocketDisconnect:
        pass
