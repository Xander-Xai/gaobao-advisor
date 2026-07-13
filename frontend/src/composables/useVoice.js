import { ref, onUnmounted } from 'vue'

export function useVoice(wsUrl) {
  const isConnected = ref(false)
  const isMuted = ref(false)
  const phase = ref('idle')
  const liveUserText = ref('')
  const liveAssistantText = ref('')
  const lastError = ref(null)
  const ws = ref(null)

  function connect(sessionId, scene, token) {
    // Backend (server/routes/voice.py) closes the socket with code 4001
    // when token is missing/invalid. Append it as a query param to satisfy
    // verify_session_token(session_id, token) on the server side.
    const params = new URLSearchParams({ session_id: sessionId, scene })
    if (token) params.set('token', token)
    const defaultBase = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`
    const base = wsUrl || import.meta.env.VITE_WS_BASE_URL || defaultBase
    const url = `${base.replace(/\/$/, '')}/api/v1/ws/call?${params.toString()}`
    ws.value = new WebSocket(url)
    ws.value.binaryType = 'arraybuffer'

    ws.value.onopen = () => {
      isConnected.value = true
      phase.value = 'listening'
      lastError.value = null
    }
    ws.value.onclose = () => {
      isConnected.value = false
      phase.value = 'idle'
    }

    ws.value.onmessage = (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data)
        if (msg.type === 'user_text') {
          liveUserText.value = msg.text
          phase.value = 'thinking'
          lastError.value = null
        }
        if (msg.type === 'assistant_text') {
          liveAssistantText.value = msg.text
          lastError.value = null
        }
        if (msg.type === 'tts_start') {
          phase.value = 'speaking'
        }
        if (msg.type === 'tts_end') {
          phase.value = 'listening'
        }
        if (msg.type === 'error') {
          lastError.value = msg.message
        }
      }
    }
  }

  function sendAudio(pcmFrame) {
    if (ws.value?.readyState === WebSocket.OPEN && !isMuted.value) {
      ws.value.send(pcmFrame)
    }
  }

  function disconnect() {
    ws.value?.close()
    isConnected.value = false
    phase.value = 'idle'
  }

  onUnmounted(disconnect)

  return {
    isConnected,
    isMuted,
    phase,
    liveUserText,
    liveAssistantText,
    lastError,
    connect,
    sendAudio,
    disconnect,
  }
}
