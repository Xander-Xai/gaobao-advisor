import { ref, onUnmounted } from 'vue'

export function useVoice(wsUrl) {
  const isConnected = ref(false)
  const isMuted = ref(false)
  const phase = ref('idle')
  const liveUserText = ref('')
  const liveAssistantText = ref('')
  const ws = ref(null)

  function connect(sessionId, scene) {
    const url = wsUrl || `ws://${location.host}/ws/call?session_id=${sessionId}&scene=${scene}`
    ws.value = new WebSocket(url)
    ws.value.binaryType = 'arraybuffer'

    ws.value.onopen = () => {
      isConnected.value = true
      phase.value = 'listening'
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
        }
        if (msg.type === 'assistant_text') {
          liveAssistantText.value = msg.text
        }
        if (msg.type === 'tts_start') {
          phase.value = 'speaking'
        }
        if (msg.type === 'tts_end') {
          phase.value = 'listening'
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
    connect,
    sendAudio,
    disconnect,
  }
}
