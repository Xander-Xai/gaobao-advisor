import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminApiError, adminApi } from '../admin'

interface FetchCall {
  url: string
  init: RequestInit & { headers: Record<string, string> }
}

function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    text: () => Promise.resolve(JSON.stringify(body)),
  }
}

function installFetch(handler: (url: string, init: RequestInit) => ReturnType<typeof response>) {
  const calls: FetchCall[] = []
  const mock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    const headers = (init.headers ?? {}) as Record<string, string>
    calls.push({ url, init: { ...init, headers } })
    return handler(url, init)
  })
  vi.stubGlobal('fetch', mock)
  return calls
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('adminApi', () => {
  it('logs in and parses the token response', async () => {
    const calls = installFetch(() =>
      response({
        access_token: 'v1.payload.signature',
        token_type: 'bearer',
        expires_in: 3600,
        user: { username: 'operator', role: 'operator' },
      }),
    )
    const result = await adminApi.login('operator', 'password123')
    expect(result.user.role).toBe('operator')
    expect(calls[0].url).toBe('/api/v1/admin/auth/login')
    expect(calls[0].init.method).toBe('POST')
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ username: 'operator', password: 'password123' })
  })

  it('maps structured errors to AdminApiError', async () => {
    installFetch(() =>
      response({ code: 'INVALID_CREDENTIALS', message: '用户名或密码错误', request_id: 'req-1' }, 401),
    )
    await expect(adminApi.login('operator', 'wrong-password')).rejects.toMatchObject({
      name: 'AdminApiError',
      code: 'INVALID_CREDENTIALS',
      status: 401,
      requestId: 'req-1',
    })
  })

  it('adds bearer auth and query parameters for schools', async () => {
    const calls = installFetch(() =>
      response({ items: [], total: 0, page: 1, page_size: 10, pages: 0 }),
    )
    await adminApi.schools({ q: '北辰', province: '示例省·甲', page: 2, page_size: 10 }, 'token-abc')
    expect(calls[0].init.headers.Authorization).toBe('Bearer token-abc')
    expect(calls[0].url).toContain('/api/v1/admin/schools?')
    expect(calls[0].url).toContain('q=%E5%8C%97%E8%BE%B0')
    expect(calls[0].url).toContain('page=2')
  })

  it('sends Idempotency-Key and filters when creating a job', async () => {
    const calls = installFetch(() =>
      response(
        {
          job: { id: 7, status: 'SUCCEEDED' },
          replayed: false,
          queue_state: 'INLINE',
          warning: null,
        },
        201,
      ),
    )
    await adminApi.createJob({ province: '示例省·甲' }, 'idem-key-123456', 'token-abc')
    expect(calls[0].init.headers['Idempotency-Key']).toBe('idem-key-123456')
    expect(calls[0].init.headers.Authorization).toBe('Bearer token-abc')
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ filters: { province: '示例省·甲' } })
  })

  it('surfaces network failures as AdminApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('offline')),
    )
    await expect(adminApi.stats('token')).rejects.toBeInstanceOf(AdminApiError)
  })
})
