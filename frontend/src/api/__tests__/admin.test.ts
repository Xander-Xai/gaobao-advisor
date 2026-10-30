import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ContractError, fetchHealth, fetchSchools } from '../admin'

const filters = { schoolName: '', province: '', level: '' }
const health = {
  status: 'ok',
  database: 'connected',
  version: '3.0.0',
  data_profile: 'SYNTHETIC_DEMO',
  optional_services: { rag: { state: 'RAG_ENABLED', documents: 31 } },
  degraded_services: [],
}
const school = { id: 1, name: '演示大学', province: '广东', city: '广州', level: '普通', school_type: '综合', ranking: null }

function mockJson(body: unknown, status = 200) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

beforeEach(() => vi.unstubAllGlobals())

describe('typed admin API', () => {
  it('reads actual health contract and preserves degraded RAG status', async () => {
    mockJson({ ...health, optional_services: { rag: { state: 'RAG_DISABLED', reason: 'No corpus' } }, degraded_services: ['rag'] })
    const result = await fetchHealth()
    expect(result.optional_services.rag?.state).toBe('RAG_DISABLED')
    expect(result.degraded_services).toEqual(['rag'])
  })

  it('fails closed on malformed health responses', async () => {
    mockJson({ status: 'ok' })
    await expect(fetchHealth()).rejects.toBeInstanceOf(ContractError)
  })

  it('sends filters and opaque cursor as encoded query parameters', async () => {
    const fetchMock = mockJson({ items: [school], next_cursor: 'id:1', has_more: true })
    const result = await fetchSchools({ schoolName: '', province: '广东', level: '普通' }, 'id:0', 10)
    expect(result.items[0].name).toBe('演示大学')
    expect(result.hasMore).toBe(true)
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('province=%E5%B9%BF%E4%B8%9C')
    expect(url).toContain('level=%E6%99%AE%E9%80%9A')
    expect(url).toContain('cursor=id%3A0')
  })

  it('normalizes single-match school name response without pagination', async () => {
    const fetchMock = mockJson({ count: 1, results: [school] })
    const result = await fetchSchools({ ...filters, schoolName: '演示' }, 'should-not-send')
    expect(result.nameSearch).toBe(true)
    expect(result.hasMore).toBe(false)
    expect((fetchMock.mock.calls[0] as [string])[0]).not.toContain('cursor=')
  })

  it('rejects malformed paginated responses instead of treating them as empty', async () => {
    mockJson({ items: [school], has_more: true, next_cursor: null })
    await expect(fetchSchools(filters)).rejects.toBeInstanceOf(ContractError)
  })

  it('surfaces HTTP failures and never fabricates data', async () => {
    mockJson({ detail: 'error' }, 503)
    await expect(fetchSchools(filters)).rejects.toThrow('HTTP 503')
  })

  it('propagates AbortSignal to fetch', async () => {
    const fetchMock = mockJson(health)
    const controller = new AbortController()
    await fetchHealth(controller.signal)
    expect((fetchMock.mock.calls[0] as [string, RequestInit])[1].signal).toBe(controller.signal)
  })
})
