import { describe, it, expect, vi, beforeEach } from 'vitest'
import { chatAPI } from '../client'

/**
 * SSE parser reliability.
 *
 * The backend emits newline-delimited `data: {json}\n\n` frames over a
 * chunked HTTP stream. A single read() may deliver a partial line (a JSON
 * object cut in half) and UTF-8 multibyte characters may straddle a chunk
 * boundary. Neither case may drop or corrupt an event.
 */

function streamOf(chunks) {
  let i = 0
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: () =>
          Promise.resolve(i < chunks.length ? { done: false, value: chunks[i++] } : { done: true }),
      }),
    },
  }
}

function encode(str) {
  return new TextEncoder().encode(str)
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('chatAPI.send SSE parser', () => {
  it('reassembles a JSON event split across arbitrary chunk boundaries', async () => {
    const full = 'data: {"type":"token","content":"你好世界"}\n\ndata: {"type":"done","session_id":"s","session_token":"t"}\n\n'
    // Cut at deliberately awkward positions inside the JSON payloads.
    const chunks = [encode(full.slice(0, 12)), encode(full.slice(12, 20)), encode(full.slice(20, 55)), encode(full.slice(55))]
    global.fetch = vi.fn().mockResolvedValue(streamOf(chunks))

    const events = await chatAPI.send('s', 'hi')
    expect(events).toHaveLength(2)
    expect(events[0]).toEqual({ type: 'token', content: '你好世界' })
    expect(events[1].type).toBe('done')
  })

  it('decodes a multibyte UTF-8 character split across chunks', async () => {
    const bytes = encode('data: {"type":"token","content":"好"}\n\n')
    const splitAt = bytes.indexOf(0xe5) + 1 // middle of the 3-byte '好'
    const chunks = [bytes.slice(0, splitAt), bytes.slice(splitAt)]
    global.fetch = vi.fn().mockResolvedValue(streamOf(chunks))

    const events = await chatAPI.send('s', 'hi')
    expect(events).toHaveLength(1)
    expect(events[0].content).toBe('好')
    expect(events[0].content).not.toContain('\uFFFD')
  })

  it('keeps a trailing partial line until its terminator arrives', async () => {
    const chunks = [encode('data: {"type":"done","session_id":"s","session_token":"t"}'), encode('\n\n')]
    global.fetch = vi.fn().mockResolvedValue(streamOf(chunks))

    const events = await chatAPI.send('s', 'hi')
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('done')
  })

  it('parses multiple frames delivered in one chunk', async () => {
    const chunk = encode('data: {"type":"slots","data":{"a":1}}\n\ndata: {"type":"done"}\n\n')
    global.fetch = vi.fn().mockResolvedValue(streamOf([chunk]))

    const events = await chatAPI.send('s', 'hi')
    expect(events.map(e => e.type)).toEqual(['slots', 'done'])
  })
})
