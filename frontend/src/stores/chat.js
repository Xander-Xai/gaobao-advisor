import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { chatAPI } from '../api/client'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const isStreaming = ref(false)
  const slots = ref({})
  // HMAC session token returned by the backend in the SSE `done` event.
  // Required to call /api/v1/profile/* and the /ws/call voice endpoint.
  const sessionToken = ref(null)
  const sessionTokens = ref({}) // Private, in-memory credentials by server-owned session ID.
  watch(currentSessionId, id => { sessionToken.value = id ? (sessionTokens.value[id] || null) : null })

  function createSession(scene = 'gaokao') {
    const id = `session-${Date.now()}`
    sessions.value.unshift({ id, scene, title: '新对话', createdAt: new Date() })
    currentSessionId.value = id
    sessionToken.value = null // Never reuse a previous session's capability token.
    slots.value = {}
    messages.value = []
    return id
  }

  async function sendMessage(text) {
    if (isStreaming.value) return // Only one in-flight stream owns this global message view.
    if (!currentSessionId.value) createSession()
    const initiatingId = currentSessionId.value
    const credential = sessionTokens.value[initiatingId] || null
    isStreaming.value = true
    messages.value.push({ role: 'user', content: text })
    let assistantContent = ''
    try {
      const events = await chatAPI.send(initiatingId, text, slots.value, 'gaokao', credential)
      for (const event of events) {
        if (event.type === 'done') {
          // A different session may have been selected while fetch was in-flight.
          // Only update the session which *initiated* the request.
          const issuedId = event.session_id || initiatingId
          const entry = sessions.value.find(s => s.id === initiatingId)
          if (entry) entry.id = issuedId
          if (event.session_token) sessionTokens.value[issuedId] = event.session_token
          if (currentSessionId.value === initiatingId) {
            currentSessionId.value = issuedId
            sessionToken.value = event.session_token || null
          }
          continue
        }
        // Never write one session's reply or slots into a newly selected session.
        if (currentSessionId.value !== initiatingId) continue
        if (event.type === 'token') {
          assistantContent += event.content
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') {
            last.content = assistantContent
          } else {
            messages.value.push({
              role: 'assistant',
              content: assistantContent,
              qualityGrade: null,
              rewritten: false,
            })
          }
        } else if (event.type === 'slots') {
          slots.value = event.data
        } else if (event.type === 'quality') {
          // Quality grade from SSE stream
          const last = messages.value[messages.value.length - 1]
          if (last?.role === 'assistant') {
            last.qualityGrade = event.grade || null
            last.rewritten = event.rewritten || false
          }
        }
      }
    } catch {
      if (currentSessionId.value === initiatingId) {
        messages.value.push({ role: 'assistant', content: '抱歉，服务暂时不可用。', qualityGrade: null, rewritten: false })
      }
    } finally {
      isStreaming.value = false
    }
  }

  return {
    sessions,
    currentSessionId,
    messages,
    isStreaming,
    slots,
    sessionToken,
    createSession,
    sendMessage,
  }
})
