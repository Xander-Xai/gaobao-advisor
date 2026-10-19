import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from '../chat'

/**
 * End-to-end incremental-render proof.
 *
 * These tests exercise the REAL client (`chatAPI`) against a *gated* stream
 * whose reads are released by the test, so we can assert what the UI has
 * rendered while the stream is still open. They deliberately do NOT mock the
 * client and do NOT simulate streaming with a per-character loop.
 */

const encoder = new TextEncoder()

function frame(event) {
  return encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
}

/**
 * A reader whose `read()` resolves only when the test pushes a chunk (or
 * closes the stream). This models a real network stream with controllable
 * timing instead of an already-buffered array.
 */
function createGatedStream() {
  const queue = []
  let waiting = null
  let closed = false
  const reader = {
    read() {
      if (queue.length) return Promise.resolve({ done: false, value: queue.shift() })
      if (closed) return Promise.resolve({ done: true })
      return new Promise(resolve => {
        waiting = resolve
      })
    },
  }
  return {
    reader,
    push(chunk) {
      if (waiting) {
        const resolve = waiting
        waiting = null
        resolve({ done: false, value: chunk })
      } else {
        queue.push(chunk)
      }
    },
    close() {
      closed = true
      if (waiting) {
        const resolve = waiting
        waiting = null
        resolve({ done: true })
      }
    },
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  setActivePinia(createPinia())
})

describe('chat incremental rendering (real client + gated stream)', () => {
  it('renders the first token while the stream is still open, before done', async () => {
    const stream = createGatedStream()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => stream.reader },
    })

    const store = useChatStore()
    store.createSession()
    const pending = store.sendMessage('你好')

    // Release only the first token; the stream stays open (no done yet).
    stream.push(frame({ type: 'token', content: '首块' }))

    await vi.waitFor(() => {
      const last = store.messages.at(-1)
      expect(last?.role).toBe('assistant')
      expect(last?.content).toBe('首块')
    })
    expect(store.isStreaming).toBe(true)
    expect(store.sessionToken).toBeNull()

    // Now finish the stream.
    stream.push(frame({ type: 'done', session_id: 'session-live', session_token: 'tok-live' }))
    stream.close()
    await pending

    expect(store.isStreaming).toBe(false)
    expect(store.sessionToken).toBe('tok-live')
    expect(store.messages.at(-1).content).toBe('首块')
  })

  it('marks the partial assistant reply incomplete when the connection drops', async () => {
    const stream = createGatedStream()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => stream.reader },
    })

    const store = useChatStore()
    store.createSession()
    const pending = store.sendMessage('你好')

    stream.push(frame({ type: 'token', content: '部分内容' }))
    await vi.waitFor(() => expect(store.messages.at(-1)?.content).toBe('部分内容'))

    stream.close() // connection ends without ever sending done
    await pending

    expect(store.isStreaming).toBe(false)
    expect(store.lastError).toBeTruthy()
    expect(store.messages.at(-1).incomplete).toBe(true)
    expect(store.sessionToken).toBeNull()
  })

  it('marks the assistant message as error when the network throws mid-stream', async () => {
    let reads = 0
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: {
        getReader: () => ({
          read: () => {
            reads += 1
            if (reads === 1) return Promise.resolve({ done: false, value: frame({ type: 'token', content: '开头' }) })
            return Promise.reject(new Error('network reset'))
          },
        }),
      },
    })

    const store = useChatStore()
    store.createSession()
    await store.sendMessage('你好')

    const last = store.messages.at(-1)
    expect(last.role).toBe('assistant')
    expect(last.content).toContain('开头')
    expect(last.incomplete).toBe(true)
    expect(store.lastError).toBeTruthy()
  })
})
