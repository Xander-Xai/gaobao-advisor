import { defineStore } from 'pinia'
import { ref } from 'vue'
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
    if (!currentSessionId.value) createSession()
    isStreaming.value = true
    messages.value.push({ role: 'user', content: text })
    let assistantContent = ''
    try {
      const events = await chatAPI.send(currentSessionId.value, text, slots.value, 'gaokao', sessionToken.value)
      for (const event of events) {
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
        } else if (event.type === 'done') {
          // Anonymous first request is assigned a server-owned, random ID.
          // Store that ID and its matching capability token together.
          if (event.session_id && event.session_id !== currentSessionId.value) {
            const previousId = currentSessionId.value
            const entry = sessions.value.find(s => s.id === previousId)
            if (entry) entry.id = event.session_id
            currentSessionId.value = event.session_id
          }
          if (event.session_token) sessionToken.value = event.session_token
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
      messages.value.push({ role: 'assistant', content: '抱歉，服务暂时不可用。', qualityGrade: null, rewritten: false })
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
