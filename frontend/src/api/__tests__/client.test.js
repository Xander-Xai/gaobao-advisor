import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  dataAPI,
  knowledgeAPI,
  profileAPI,
  reportAPI,
  healthAPI,
  feedbackAPI,
  highlightAPI,
  onboardingAPI,
} from '../client'

/**
 * Test the unified API client envelopes without touching the network.
 *
 * Each test sets up a mock `fetch` that returns a predetermined Response,
 * then asserts the client surfaces the right shape (`{data, error}`),
 * path/query string, method, and (for profile) Authorization header.
 */

function mockFetchResponse({ ok = true, status = 200, body = {} } = {}) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('envelope shape', () => {
  it('returns {data, error:null} on HTTP 200', async () => {
    global.fetch = mockFetchResponse({ body: { status: 'ok' } })
    const { data, error } = await healthAPI.check()
    expect(error).toBeNull()
    expect(data).toEqual({ status: 'ok' })
  })

  it('returns {data:null, error:{...}} on HTTP 4xx', async () => {
    global.fetch = mockFetchResponse({ ok: false, status: 404, body: { detail: '报告不存在' } })
    const { data, error } = await reportAPI.fetch('nope')
    expect(data).toBeNull()
    expect(error.status).toBe(404)
    expect(error.message).toBe('报告不存在')
  })

  it('returns NETWORK_ERROR when fetch throws', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('offline'))
    const { data, error } = await healthAPI.check()
    expect(data).toBeNull()
    expect(error.code).toBe('NETWORK_ERROR')
  })
})

describe('dataAPI', () => {
  it('searchSchools builds correct query for school_name', async () => {
    const fetchMock = mockFetchResponse({ body: { count: 1, results: [{ name: '清华大学' }] } })
    global.fetch = fetchMock
    const { data } = await dataAPI.searchSchools({ schoolName: '清华' })
    expect(data.count).toBe(1)
    const [url] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/data/schools')
    expect(url).toContain('school_name=%E6%B8%85%E5%8D%8E')
  })

  it('getScores passes all query params', async () => {
    const fetchMock = mockFetchResponse({ body: { items: [] } })
    global.fetch = fetchMock
    await dataAPI.getScores({ schoolName: '清华', province: '北京', year: 2024, major: '计算机' })
    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('school_name=')
    expect(url).toContain('province=%E5%8C%97%E4%BA%AC')
    expect(url).toContain('year=2024')
    expect(url).toContain('major=')
  })

  it('getPlans drops empty province/year params', async () => {
    const fetchMock = mockFetchResponse({ body: { items: [] } })
    global.fetch = fetchMock
    await dataAPI.getPlans({ schoolName: '清华' })
    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('school_name=')
    expect(url).not.toContain('province=')
    expect(url).not.toContain('year=')
  })
})

describe('knowledgeAPI', () => {
  it('search POSTs {query, groups, top_k}', async () => {
    const fetchMock = mockFetchResponse({ body: { count: 0, chunks: [] } })
    global.fetch = fetchMock
    await knowledgeAPI.search({ query: '位次法', groups: ['G1'], topK: 3 })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/knowledge/search')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ query: '位次法', groups: ['G1'], top_k: 3 })
  })

  it('getQuotes appends ?major= query', async () => {
    const fetchMock = mockFetchResponse({ body: { count: 0, quotes: [] } })
    global.fetch = fetchMock
    await knowledgeAPI.getQuotes({ major: '计算机', topK: 5 })
    const url = fetchMock.mock.calls[0][0]
    expect(url).toContain('/api/v1/knowledge/quotes')
    expect(url).toContain('major=')
  })
})

describe('profileAPI (Bearer auth)', () => {
  it('injects Authorization: Bearer <token> on GET', async () => {
    const fetchMock = mockFetchResponse({ body: { session_id: 's1', profile: {}, is_complete: false, missing_fields: [] } })
    global.fetch = fetchMock
    await profileAPI.get('s1', 'tok-abc')
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer tok-abc')
  })

  it('update PUTs {field, value} body', async () => {
    const fetchMock = mockFetchResponse({ body: { ok: true } })
    global.fetch = fetchMock
    await profileAPI.update('s1', { field: 'province', value: '山东' }, 'tok-abc')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/profile/s1')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body)).toEqual({ field: 'province', value: '山东' })
  })

  it('skip POSTs to /skip endpoint', async () => {
    const fetchMock = mockFetchResponse({ body: { status: 'skipped' } })
    global.fetch = fetchMock
    await profileAPI.skip('s1', { field: 'region' }, 'tok-abc')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/profile/s1/skip')
    expect(init.method).toBe('POST')
  })
})

describe('reportAPI', () => {
  it('generate POSTs {session_id, student_name}', async () => {
    const fetchMock = mockFetchResponse({ body: { report_id: 'r1', status: 'completed' } })
    global.fetch = fetchMock
    const { data } = await reportAPI.generate({ sessionId: 's1', studentName: '小明' })
    expect(data.report_id).toBe('r1')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/report/generate')
    expect(JSON.parse(init.body)).toEqual({ session_id: 's1', student_name: '小明' })
  })
})

describe('chat metadata APIs', () => {
  it('feedbackAPI.submit sends {session_id, message_index, rating, ...}', async () => {
    const fetchMock = mockFetchResponse({ body: { success: true } })
    global.fetch = fetchMock
    await feedbackAPI.submit({ sessionId: 's1', messageIndex: 2, rating: 'helpful' })
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body)
    expect(body).toMatchObject({ session_id: 's1', message_index: 2, rating: 'helpful' })
  })

  it('highlightAPI.submit defaults score to 80', async () => {
    const fetchMock = mockFetchResponse({ body: { success: true } })
    global.fetch = fetchMock
    await highlightAPI.submit({ sessionId: 's1', content: '一段金句' })
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body)
    expect(body.score).toBe(80)
    expect(body.content).toBe('一段金句')
  })
})

describe('onboardingAPI', () => {
  it('step posts {step, data}', async () => {
    const fetchMock = mockFetchResponse({ body: { step: 1, missing: [] } })
    global.fetch = fetchMock
    await onboardingAPI.step(1, { province: '山东' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/onboarding')
    expect(JSON.parse(init.body)).toEqual({ step: 1, data: { province: '山东' } })
  })
})
