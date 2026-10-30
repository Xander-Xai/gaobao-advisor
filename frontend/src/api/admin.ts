/**
 * Read-only public demo workbench API.
 * These endpoints have no administrator authorization contract. Never use this
 * module to claim privileged admin access or expose private student data.
 */
export interface HealthSnapshot {
  status: 'ok' | 'degraded'
  database: 'connected' | 'disconnected'
  version: string
  data_profile: string
  optional_services: {
    rag?: {
      state: string
      reason?: string
      documents?: number
      chunks?: number
      integrity_ok?: boolean
    }
  }
  degraded_services: string[]
}

export interface School {
  id: number
  name: string
  province: string
  city: string
  level: string
  school_type: string
  ranking: number | null
}

export interface SchoolFilters {
  schoolName: string
  province: string
  level: string
}

export interface SchoolPage {
  items: School[]
  nextCursor: string | null
  hasMore: boolean
  nameSearch: boolean
}

const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export class ContractError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ContractError'
  }
}

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error('网络连接失败，请检查服务是否可用')
  }
  if (!response.ok) {
    throw new Error(`请求失败 (HTTP ${response.status})`)
  }
  try {
    return await response.json() as unknown
  } catch {
    throw new ContractError('服务返回的数据不是有效的 JSON')
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthSnapshot> {
  const body = await getJson('/health', signal)
  if (!record(body) ||
      (body.status !== 'ok' && body.status !== 'degraded') ||
      (body.database !== 'connected' && body.database !== 'disconnected') ||
      typeof body.version !== 'string' ||
      typeof body.data_profile !== 'string' ||
      !record(body.optional_services) ||
      !Array.isArray(body.degraded_services) ||
      !body.degraded_services.every((value) => typeof value === 'string')) {
    throw new ContractError('健康检查返回结构与后端契约不一致')
  }

  const rag = body.optional_services.rag
  if (rag !== undefined && (!record(rag) || typeof rag.state !== 'string')) {
    throw new ContractError('RAG 状态结构不正确')
  }

  return body as unknown as HealthSnapshot
}

function normalizeSchools(rows: unknown): School[] {
  if (!Array.isArray(rows)) {
    throw new ContractError('院校列表不是数组')
  }
  return rows.map((item: unknown) => {
    if (!record(item) ||
        !Number.isInteger(item.id) ||
        typeof item.name !== 'string' ||
        typeof item.province !== 'string') {
      throw new ContractError('院校记录结构与后端契约不一致')
    }
    return {
      id: item.id as number,
      name: item.name,
      province: item.province,
      city: typeof item.city === 'string' ? item.city : '',
      level: typeof item.level === 'string' ? item.level : '未标注',
      school_type: typeof item.school_type === 'string' ? item.school_type : '未标注',
      ranking: typeof item.ranking === 'number' ? item.ranking : null,
    }
  })
}

export async function fetchSchools(
  filters: SchoolFilters,
  cursor: string | null = null,
  limit = 10,
  signal?: AbortSignal,
): Promise<SchoolPage> {
  const params = new URLSearchParams()
  if (filters.schoolName.trim()) params.set('school_name', filters.schoolName.trim())
  if (filters.province.trim()) params.set('province', filters.province.trim())
  if (filters.level.trim()) params.set('level', filters.level.trim())
  params.set('limit', String(Math.max(1, Math.min(200, Math.trunc(limit)))))
  // school_name uses the backend's single-match search, not cursor pagination.
  if (!filters.schoolName.trim() && cursor) params.set('cursor', cursor)

  const body = await getJson(`/data/schools?${params.toString()}`, signal)
  if (!record(body)) throw new ContractError('院校查询返回结构不正确')

  if (filters.schoolName.trim()) {
    if (!Array.isArray(body.results)) {
      throw new ContractError('院校名称查询缺少 results 字段')
    }
    return { items: normalizeSchools(body.results), nextCursor: null, hasMore: false, nameSearch: true }
  }
  if (typeof body.has_more !== 'boolean' ||
      (body.next_cursor !== null && typeof body.next_cursor !== 'string') ||
      !Array.isArray(body.items) ||
      (body.has_more && (typeof body.next_cursor !== 'string' || body.next_cursor.length === 0))) {
    throw new ContractError('院校分页响应不满足游标契约')
  }
  return {
    items: normalizeSchools(body.items),
    nextCursor: body.next_cursor as string | null,
    hasMore: body.has_more,
    nameSearch: false,
  }
}
