import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatAPI } from '../api/client'
import { useSceneStore } from './scene'

const STORAGE_KEY = 'gaobao_sessions'
const TOKEN_KEY = 'gaobao_session_token'

function loadPersistedSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function persistSessions(sessions) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch {
    // localStorage full or unavailable — non-critical
  }
}

function loadPersistedMessages(sessionId) {
  try {
    const raw = localStorage.getItem(`gaobao_msg_${sessionId}`)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function persistMessages(sessionId, msgs) {
  try {
    localStorage.setItem(`gaobao_msg_${sessionId}`, JSON.stringify(msgs))
  } catch {
    // localStorage full — non-critical
  }
}

function loadPersistedToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || null
  } catch {
    return null
  }
}

function persistToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    // non-critical
  }
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref(loadPersistedSessions())
  const currentSessionId = ref(null)
  const messages = ref([])
  const isStreaming = ref(false)
  const slots = ref({})
  // HMAC session token returned by the backend in the SSE `done` event.
  // Required to call /api/v1/profile/* and the /ws/call voice endpoint.
  const sessionToken = ref(loadPersistedToken())
  const lastEmotion = ref(null)
  const lastStructuredResult = ref(null)
  const degraded = ref(false)

  function switchSession(id) {
    if (id === currentSessionId.value) return
    // Persist messages of the session we are leaving before switching.
    if (currentSessionId.value) {
      persistMessages(currentSessionId.value, messages.value)
    }
    currentSessionId.value = id
    messages.value = loadPersistedMessages(id)
  }

  function createSession(scene = 'gaokao') {
    const id = `session-${Date.now()}`
    sessions.value.unshift({ id, scene, title: '新对话', createdAt: new Date() })
    currentSessionId.value = id
    messages.value = loadPersistedMessages(id)
    persistSessions(sessions.value)
    return id
  }

  async function sendMessage(text) {
    const sceneStore = useSceneStore()
    const activeSession = sessions.value.find((session) => session.id === currentSessionId.value)
    const sceneId = sceneStore.current || activeSession?.scene || 'gaokao'
    if (!currentSessionId.value) createSession(sceneId)
    const session = sessions.value.find((item) => item.id === currentSessionId.value)
    if (session) {
      session.scene = sceneId
      persistSessions(sessions.value)
    }
    isStreaming.value = true
    degraded.value = false
    const sessionId = currentSessionId.value
    messages.value.push({ role: 'user', content: text, sessionId })
    let assistantContent = ''
    try {
      const handleEvent = (event) => {
        if (event.type === 'token') {
          assistantContent += event.content
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') {
            last.content = assistantContent
          } else {
            messages.value.push({
              role: 'assistant',
              content: assistantContent,
              sessionId,
              messageIndex: messages.value.length,
              qualityGrade: null,
              rewritten: false,
            })
          }
        } else if (event.type === 'emotion') {
          lastEmotion.value = event.state
        } else if (event.type === 'structured') {
          lastStructuredResult.value = event.result
        } else if (event.type === 'slots') {
          slots.value = event.data
        } else if (event.type === 'done') {
          // Persist the HMAC session token for subsequent profile/voice calls.
          if (event.session_token) {
            sessionToken.value = event.session_token
            persistToken(event.session_token)
          }
        } else if (event.type === 'quality') {
          // Quality grade from SSE stream
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') {
            last.qualityGrade = event.grade || null
            last.rewritten = event.rewritten || false
          }
        } else if (event.type === 'error') {
          messages.value.push({
            role: 'assistant',
            content: event.message || '抱歉，服务暂时不可用。',
            sessionId,
            messageIndex: messages.value.length,
            qualityGrade: null,
            rewritten: false,
          })
          isStreaming.value = false
          persistMessages(sessionId, messages.value)
          return
        } else if (event.type === 'degraded') {
          degraded.value = true
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') {
            last.degraded = true
          }
        }
      }
      await chatAPI.send(sessionId, text, slots.value, sceneId, handleEvent)
    } catch {
      messages.value.push({
        role: 'assistant',
        content: '抱歉，服务暂时不可用。',
        sessionId,
        messageIndex: messages.value.length,
        qualityGrade: null,
        rewritten: false,
      })
    } finally {
      isStreaming.value = false
      persistMessages(sessionId, messages.value)
    }
  }

  return {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    slots,
    sessionToken,
    lastEmotion,
    lastStructuredResult,
    degraded,
    createSession,
    switchSession,
    sendMessage,
  }
})
