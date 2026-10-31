import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { chatAPI } from '../../api/client'
import { useChatStore } from '../chat'

vi.mock('../../api/client', () => ({ chatAPI: { send: vi.fn() } }))

/**
 * Emulate the real client contract: events are dispatched through `onEvent`
 * (incrementally) and the full list is also returned. The store now relies on
 * `onEvent`, so a mock that only resolves an array would not exercise it.
 */
function mockSend(events) {
  return (sessionId, message, slots, scene, token, { onEvent } = {}) => {
    for (const event of events) onEvent?.(event)
    return Promise.resolve(events)
  }
}

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

    chatAPI.send.mockImplementationOnce(mockSend([{ type: 'done', session_id: 'session-server-one', session_token: 'token-one' }]))
    await store.sendMessage('你好')

    expect(store.currentSessionId).toBe('session-server-one')
    expect(store.sessionToken).toBe('token-one')
    expect(store.sessions[0].id).toBe('session-server-one')
    expect(store.sessions[0].id).not.toBe(placeholderId)

    chatAPI.send.mockImplementationOnce(mockSend([]))
    await store.sendMessage('继续')
    expect(chatAPI.send).toHaveBeenLastCalledWith(
      'session-server-one', '继续', {}, 'gaokao', 'token-one', expect.objectContaining({ onEvent: expect.any(Function) })
    )
  })

  it('does not steal a newly selected session when an older response completes', async () => {
    vi.spyOn(Date, 'now').mockReturnValueOnce(1000).mockReturnValueOnce(2000)
    const store = useChatStore()
    const firstId = store.createSession()

    let release
    chatAPI.send.mockImplementationOnce(
      (sessionId, message, slots, scene, token, { onEvent } = {}) =>
        new Promise(resolve => {
          release = () => {
            const events = [
              { type: 'token', content: '来自第一会话的回复' },
              { type: 'done', session_id: 'session-first-from-server', session_token: 'token-first' },
            ]
            for (const event of events) onEvent?.(event)
            resolve(events)
          }
        })
    )
    const pending = store.sendMessage('来自第一会话')
    const secondId = store.createSession()
    expect(secondId).not.toBe(firstId)

    release()
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

describe('chat stream integrity', () => {
  it('flags the turn as failed when the stream ends without a done event', async () => {
    const store = useChatStore()
    store.createSession()

    chatAPI.send.mockImplementationOnce(mockSend([{ type: 'token', content: '半截回复' }]))
    await store.sendMessage('你好')

    expect(store.isStreaming).toBe(false)
    expect(store.lastError).toBeTruthy()
    const last = store.messages.at(-1)
    expect(last.role).toBe('assistant')
    expect(last.incomplete).toBe(true)
    // No session credential may be minted without a valid done event.
    expect(store.sessionToken).toBeNull()
  })

  it('surfaces an error event and does not treat the turn as successful', async () => {
    const store = useChatStore()
    store.createSession()

    chatAPI.send.mockImplementationOnce(mockSend([{ type: 'error', code: 'GRAPH_FAILED', message: '服务暂时不可用' }]))
    await store.sendMessage('你好')

    expect(store.lastError).toBe('服务暂时不可用')
    expect(store.messages.at(-1).error).toBe(true)
    expect(store.sessionToken).toBeNull()
  })

  it('attaches degraded, sources and rag_status to the assistant message', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(555)
    const store = useChatStore()
    store.createSession()

    chatAPI.send.mockImplementationOnce(
      mockSend([
        { type: 'sources', data: [{ source: 'G1_core_method § 投档' }], has_evidence: true },
        { type: 'token', content: '根据资料……' },
        { type: 'degraded', message: '未配置 LLM Key' },
        { type: 'rag_status', state: 'NO_EVIDENCE', reason: '无匹配证据' },
        { type: 'done', session_id: 'session-meta', session_token: 'tok-meta' },
      ])
    )
    await store.sendMessage('平行志愿')

    const last = store.messages.at(-1)
    expect(last.role).toBe('assistant')
    expect(last.sources).toHaveLength(1)
    expect(last.degraded).toBe(true)
    expect(last.ragStatus).toEqual({ state: 'NO_EVIDENCE', reason: '无匹配证据' })
    expect(store.lastError).toBeNull()
  })

  it('buffers a structured event emitted before the first token', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(777)
    const store = useChatStore()
    store.createSession()

    const card = {
      title: '高考志愿规划建议',
      summary: '河北 620 分，意向计算机',
      facts: ['省份：河北', '分数：620'],
      suggestions: ['推荐：北辰示例科技大学（合成）'],
      risks: ['数据有限，建议以官方最新信息为准'],
      next_actions: ['核对招生计划'],
      sources: ['数据库位次法（合成）'],
      confidence: 0.86,
    }
    chatAPI.send.mockImplementationOnce(
      mockSend([
        { type: 'structured', result: card },
        { type: 'token', content: '根据你的信息……' },
        { type: 'done', session_id: 'session-structured', session_token: 'tok-structured' },
      ])
    )
    await store.sendMessage('河北620分想学计算机')

    const last = store.messages.at(-1)
    expect(last.role).toBe('assistant')
    expect(last.structured).toEqual(card)
    expect(store.lastError).toBeNull()
  })

  it('records a network failure as lastError instead of silently succeeding', async () => {
    const store = useChatStore()
    store.createSession()

    chatAPI.send.mockRejectedValueOnce(new Error('network down'))
    await store.sendMessage('你好')

    expect(store.lastError).toBeTruthy()
    expect(store.sessionToken).toBeNull()
  })
})
