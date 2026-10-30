import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AdminView from '../AdminView.vue'
import { useAdminStore } from '../../stores/admin'
import type {
  AdminRole,
  AdminTokenResponse,
  FilterOptions,
  Page,
  QualityJob,
  QualityJobDetail,
  SchoolListItem,
  Stats,
  SystemStatus,
} from '../../types/admin'

const stats: Stats = {
  data_profile: 'SYNTHETIC_DEMO',
  schools: 8,
  majors: 12,
  admission_scores: 128,
  enrollment_plans: 32,
  jobs_total: 1,
  jobs_by_status: { PENDING: 0, RUNNING: 0, SUCCEEDED: 1, FAILED: 0 },
  issues_by_severity: { ERROR: 1, WARNING: 2, INFO: 0 },
  schools_by_level: { '985': 1, '211': 2, 双一流: 1, 普通: 4 },
  pending_review: 1,
  audit_events: 3,
  last_job_at: '2026-10-30T10:00:00',
}

const systemStatus: SystemStatus = {
  admin_enabled: true,
  config_source: 'ADMIN_USERS_JSON',
  database_dialect: 'sqlite',
  task_mode: 'inline',
  queue_state: 'DISABLED',
  worker_hint: '同步执行（演示/测试）',
}

const filterOptions: FilterOptions = {
  provinces: ['示例省·甲', '示例省·乙'],
  levels: ['985', '211', '双一流', '普通'],
  school_types: ['综合', '理工'],
}

const school: SchoolListItem = {
  id: 1,
  name: '北辰示例科技大学（合成）',
  province: '示例省·甲',
  city: '示例市·晨',
  level: '985',
  school_type: '综合',
  ranking: 10,
  is_985: 1,
  is_211: 1,
  is_double_first_class: 1,
  special_type: 'SYNTHETIC_DEMO_DATA',
  data_source_note: '合成演示数据，无真实来源',
  score_count: 12,
  plan_count: 4,
  latest_year: 2025,
  latest_min_score: 620,
}

function page<T>(items: T[]): Page<T> {
  return { items, total: items.length, page: 1, page_size: 10, pages: items.length ? 1 : 0 }
}

const job: QualityJob = {
  id: 7,
  job_type: 'admission_data_quality',
  status: 'SUCCEEDED',
  review_status: 'PENDING_REVIEW',
  idempotency_key: 'fixture-idempotency-key',
  filters: { province: '示例省·甲' },
  requested_by: 'operator',
  execution_mode: 'inline_degraded',
  source_marker: 'SYNTHETIC_DEMO_DATA',
  attempts: 1,
  max_attempts: 3,
  version: 2,
  checked_rows: 20,
  issue_count: 1,
  error_code: null,
  error_message: null,
  review_note: null,
  reviewed_by: null,
  created_at: '2026-10-30T10:00:00',
  updated_at: '2026-10-30T10:00:01',
  started_at: '2026-10-30T10:00:00',
  finished_at: '2026-10-30T10:00:01',
  reviewed_at: null,
}

const jobDetail: QualityJobDetail = {
  job,
  issues: [
    {
      id: 1,
      rule_code: 'score_out_of_range',
      severity: 'ERROR',
      entity_type: 'admission_score',
      entity_id: 99,
      field_name: 'min_score',
      message: '最低分 900 超出 0-750 合理范围',
      suggestion: '核对原始数据并修正分数',
    },
  ],
}

function tokenResponse(role: AdminRole): AdminTokenResponse {
  return {
    access_token: `v1.payload.${role}`,
    token_type: 'bearer',
    expires_in: 3600,
    user: { username: role, role },
  }
}

function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 200 && status < 300 ? 'OK' : 'Error',
    text: () => Promise.resolve(JSON.stringify(body)),
  }
}

interface RouterOptions {
  role?: AdminRole
  schools?: SchoolListItem[]
  failSchools?: number
  audit?: boolean
}

function installRouter(options: RouterOptions = {}) {
  const role = options.role ?? 'operator'
  const calls: Array<{ url: string; init: RequestInit }> = []
  let schoolFailures = options.failSchools ?? 0
  const mock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    calls.push({ url, init })
    const path = url.split('?')[0]
    if (path.endsWith('/admin/auth/login')) return response(tokenResponse(role))
    if (path.endsWith('/admin/auth/me')) return response({ username: role, role })
    if (path.endsWith('/admin/stats')) return response(stats)
    if (path.endsWith('/admin/system/status')) return response(systemStatus)
    if (path.endsWith('/admin/schools/filters')) return response(filterOptions)
    if (path.endsWith('/admin/schools/1')) {
      return response({ ...school, website: null, description: '合成院校', scores: [], plans: [] })
    }
    if (path.endsWith('/admin/schools')) {
      if (schoolFailures > 0) {
        schoolFailures -= 1
        return response({ code: 'INTERNAL_ERROR', message: '数据库暂时不可用', request_id: 'req-fail' }, 500)
      }
      return response(page(options.schools ?? [school]))
    }
    if (path.endsWith('/admin/quality/jobs') && init.method === 'POST') {
      return response({ job, replayed: false, queue_state: 'INLINE', warning: '已同步执行' }, 201)
    }
    if (path.endsWith('/admin/quality/jobs/7')) return response(jobDetail)
    if (path.endsWith('/admin/quality/jobs')) return response(page([job]))
    if (path.endsWith('/admin/quality/jobs/7/review')) {
      return response({ ...job, review_status: 'APPROVED', reviewed_by: role, version: 3 })
    }
    if (path.endsWith('/admin/audit-logs')) {
      return response(
        page([
          {
            id: 1,
            request_id: 'req-1',
            actor: 'admin',
            role: 'admin',
            action: 'quality_job.reviewed',
            resource_type: 'data_quality_job',
            resource_id: '7',
            outcome: 'SUCCESS',
            detail: { decision: 'APPROVED' },
            created_at: '2026-10-30T10:00:00',
          },
        ]),
      )
    }
    return response({ code: 'NOT_FOUND', message: `unmocked ${path}` }, 404)
  })
  vi.stubGlobal('fetch', mock)
  return calls
}

async function mountAndLogin(role: AdminRole = 'operator') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
  await wrapper.find('[data-testid="admin-username"]').setValue(role)
  await wrapper.find('[data-testid="admin-password"]').setValue('password123')
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  window.sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('AdminView access control', () => {
  it('shows the login form without a token', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
    expect(wrapper.find('[data-testid="admin-username"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tab-data"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('匿名聊天会话令牌不能访问后台')
  })

  it('shows login errors from the API', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        response({ code: 'INVALID_CREDENTIALS', message: '用户名或密码错误', request_id: 'req' }, 401),
      ),
    )
    const wrapper = mount(AdminView, { global: { plugins: [pinia] } })
    await wrapper.find('[data-testid="admin-username"]').setValue('operator')
    await wrapper.find('[data-testid="admin-password"]').setValue('password123')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[data-testid="login-error"]').text()).toContain('用户名或密码错误')
    expect(useAdminStore().isAuthenticated).toBe(false)
  })

  it('hides audit and disables writes for viewer', async () => {
    installRouter({ role: 'viewer' })
    const wrapper = await mountAndLogin('viewer')
    expect(wrapper.find('[data-testid="tab-audit"]').exists()).toBe(false)
    await wrapper.find('[data-testid="tab-quality"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="create-job"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('只能查看')
  })
})

describe('AdminView data workflow', () => {
  it('renders real API data after login', async () => {
    installRouter()
    const wrapper = await mountAndLogin('operator')
    expect(wrapper.find('[data-testid="admin-user"]').text()).toContain('operator')
    expect(wrapper.text()).toContain('北辰示例科技大学（合成）')
    expect(wrapper.text()).toContain('共 1 条')
    expect(wrapper.text()).toContain('SYNTHETIC_DEMO')
  })

  it('sends the selected filter to the API', async () => {
    const calls = installRouter()
    const wrapper = await mountAndLogin('operator')
    await wrapper.find('[data-testid="school-keyword"]').setValue('北辰')
    await wrapper.find('[data-testid="school-province"]').setValue('示例省·甲')
    await wrapper.find('[data-testid="toggle-order"]').trigger('click')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const filtered = calls.filter((call) => call.url.includes('/admin/schools?'))
    const last = filtered[filtered.length - 1]
    expect(last.url).toContain('q=%E5%8C%97%E8%BE%B0')
    expect(last.url).toContain('province=%E7%A4%BA%E4%BE%8B%E7%9C%81%C2%B7%E7%94%B2')
    expect(last.url).toContain('order=desc')
  })

  it('shows an empty state instead of a blank table', async () => {
    installRouter({ schools: [] })
    const wrapper = await mountAndLogin('operator')
    expect(wrapper.find('[data-testid="schools-empty"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('没有匹配的院校')
  })

  it('shows an error and retries the request', async () => {
    installRouter({ failSchools: 1 })
    const wrapper = await mountAndLogin('operator')
    expect(wrapper.find('[data-testid="schools-error"]').exists()).toBe(true)
    await wrapper.find('[data-testid="schools-error"] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="schools-error"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('北辰示例科技大学（合成）')
  })

  it('creates a job and shows the returned findings', async () => {
    const calls = installRouter()
    const wrapper = await mountAndLogin('operator')
    await wrapper.find('[data-testid="tab-quality"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="create-job"]').trigger('click')
    await flushPromises()
    await flushPromises()
    const posts = calls.filter((call) => call.url.endsWith('/admin/quality/jobs') && call.init.method === 'POST')
    expect(posts).toHaveLength(1)
    expect((posts[0].init.headers as Record<string, string>)['Idempotency-Key']).toBeTruthy()
    expect(wrapper.find('[data-testid="quality-notice"]').text()).toContain('已同步执行')
    expect(wrapper.find('[data-testid="job-detail"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('score_out_of_range')
  })

  it('lets an admin review a succeeded job', async () => {
    const calls = installRouter({ role: 'admin' })
    const wrapper = await mountAndLogin('admin')
    await wrapper.find('[data-testid="tab-quality"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="create-job"]').trigger('click')
    await flushPromises()
    await flushPromises()
    const note = wrapper.find('#review-note')
    expect(note.exists()).toBe(true)
    await note.setValue('复核通过')
    await wrapper.find('[data-testid="review-approve"]').trigger('click')
    await flushPromises()
    const reviews = calls.filter((call) => call.url.endsWith('/quality/jobs/7/review'))
    expect(reviews).toHaveLength(1)
    expect(JSON.parse(String(reviews[0].init.body))).toMatchObject({
      decision: 'APPROVED',
      note: '复核通过',
      expected_version: 2,
    })
    expect(wrapper.find('[data-testid="quality-notice"]').text()).toContain('审核通过')
  })

  it('shows audit logs for admins', async () => {
    installRouter({ role: 'admin' })
    const wrapper = await mountAndLogin('admin')
    expect(wrapper.find('[data-testid="tab-audit"]').exists()).toBe(true)
    await wrapper.find('[data-testid="tab-audit"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('quality_job.reviewed')
    expect(wrapper.text()).toContain('req-1')
  })
})
