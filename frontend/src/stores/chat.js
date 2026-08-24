import { defineStore } from 'pinia'
import { ref } from 'vue'
import { chatAPI } from '../api/client'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const isStreaming = ref(false)
  const slots = ref({})
  const sessionToken = ref(null)

  async function createSession(scene = 'gaokao') {
    const { data, error } = await chatAPI.createSession(scene)
    if (error || !data?.session_id || !data?.session_token) {
      throw new Error(error?.message || 'Failed to create chat session')
    }

    const session = {
      id: data.session_id,
      token: data.session_token,
      scene: data.scene || scene,
      title: '新对话',
      createdAt: new Date(),
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    sessionToken.value = session.token
    messages.value = []
    slots.value = {}
    return session.id
  }

  function selectSession(sessionId) {
    const session = sessions.value.find((item) => item.id === sessionId)
    if (!session) return
    currentSessionId.value = session.id
    sessionToken.value = session.token || null
    // Conversation message restoration is not implemented yet; avoid showing
    // messages from a different session when switching.
    messages.value = []
    slots.value = {}
  }

  function updateCurrentSessionToken(token) {
    if (!token) return
    sessionToken.value = token
    const session = sessions.value.find((item) => item.id === currentSessionId.value)
    if (session) session.token = token
  }

  async function sendMessage(text) {
    if (!currentSessionId.value || !sessionToken.value) await createSession()
    isStreaming.value = true
    messages.value.push({ role: 'user', content: text })
    let assistantContent = ''
    const assistantMessageIndex = messages.value.filter((message) => message.role === 'assistant').length

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
            sessionId: currentSessionId.value,
            messageIndex: assistantMessageIndex,
            qualityGrade: null,
            rewritten: false,
          })
        }
      } else if (event.type === 'slots') {
        slots.value = event.data
      } else if (event.type === 'done') {
        updateCurrentSessionToken(event.session_token)
      } else if (event.type === 'quality') {
        const last = messages.value[messages.value.length - 1]
        if (last?.role === 'assistant') {
          last.qualityGrade = event.grade || null
          last.rewritten = event.rewritten || false
        }
      }
    }

    try {
      const currentSession = sessions.value.find((item) => item.id === currentSessionId.value)
      const scene = currentSession?.scene || 'gaokao'
      await chatAPI.send(
        currentSessionId.value,
        text,
        slots.value,
        scene,
        handleEvent,
        sessionToken.value,
      )
    } catch {
      const last = messages.value[messages.value.length - 1]
      if (last?.role === 'assistant' && assistantContent) {
        last.content = `${assistantContent}\n\n[连接中断，请重试]`
      } else {
        messages.value.push({
          role: 'assistant',
          content: '抱歉，服务暂时不可用。',
          sessionId: currentSessionId.value,
          messageIndex: assistantMessageIndex,
          qualityGrade: null,
          rewritten: false,
        })
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
    selectSession,
    sendMessage,
  }
})
