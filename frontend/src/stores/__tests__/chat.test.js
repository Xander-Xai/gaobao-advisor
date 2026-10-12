import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { chatAPI } from '../../api/client'
import { useChatStore } from '../chat'

vi.mock('../../api/client', () => ({ chatAPI: { send: vi.fn() } }))

beforeEach(() => {
  vi.restoreAllMocks()
  vi.resetAllMocks()
  setActivePinia(createPinia())
})

describe('chat session ownership', () => {
  it('keeps a server-assigned ID and token paired across messages', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(12345)
    const store = useChatStore()
    const placeholderId = store.createSession()

    chatAPI.send.mockResolvedValueOnce([
      { type: 'done', session_id: 'session-server-one', session_token: 'token-one' },
    ])
    await store.sendMessage('你好')

    expect(store.currentSessionId).toBe('session-server-one')
    expect(store.sessionToken).toBe('token-one')
    expect(store.sessions[0].id).toBe('session-server-one')
    expect(store.sessions[0].id).not.toBe(placeholderId)

    chatAPI.send.mockResolvedValueOnce([])
    await store.sendMessage('继续')
    expect(chatAPI.send).toHaveBeenLastCalledWith(
      'session-server-one', '继续', {}, 'gaokao', 'token-one'
    )
  })

  it('does not steal a newly selected session when an older response completes', async () => {
    vi.spyOn(Date, 'now').mockReturnValueOnce(1000).mockReturnValueOnce(2000)
    const store = useChatStore()
    const firstId = store.createSession()

    let finishRequest
    chatAPI.send.mockImplementationOnce(() => new Promise(resolve => {
      finishRequest = resolve
    }))
    const pending = store.sendMessage('来自第一会话')
    const secondId = store.createSession()
    expect(secondId).not.toBe(firstId)

    finishRequest([
      { type: 'token', content: '来自第一会话的回复' },
      { type: 'done', session_id: 'session-first-from-server', session_token: 'token-first' },
    ])
    await pending

    expect(store.currentSessionId).toBe(secondId)
    expect(store.sessionToken).toBeNull()
    expect(store.sessions.some(s => s.id === 'session-first-from-server')).toBe(true)
    expect(store.sessions.some(s => s.id === secondId)).toBe(true)
    expect(store.messages).toEqual([])

    store.currentSessionId = 'session-first-from-server'
    await nextTick()
    expect(store.sessionToken).toBe('token-first')
  })
})
