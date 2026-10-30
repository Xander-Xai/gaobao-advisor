import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminView from '../AdminView.vue'
import { fetchHealth, fetchSchools } from '../../api/admin'

vi.mock('../../api/admin', () => ({
  fetchHealth: vi.fn(),
  fetchSchools: vi.fn(),
}))

const school = { id: 1, name: '演示大学', province: '广东', city: '广州', level: '普通', school_type: '综合', ranking: null }
const health = {
  status: 'ok',
  database: 'connected',
  version: '3.0.0',
  data_profile: 'SYNTHETIC_DEMO',
  optional_services: { rag: { state: 'RAG_ENABLED' } },
  degraded_services: [],
}

function mountView() {
  return mount(AdminView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(fetchHealth).mockResolvedValue(health as Awaited<ReturnType<typeof fetchHealth>>)
  vi.mocked(fetchSchools).mockResolvedValue({ items: [school], nextCursor: '2', hasMore: true, nameSearch: false })
})

describe('read-only school workbench', () => {
  it('renders health, real API school data and synthetic-data warning', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('演示大学')
    expect(wrapper.text()).toContain('SYNTHETIC_DEMO')
    expect(wrapper.text()).toContain('不代表管理员权限')
    wrapper.unmount()
  })

  it('applies filters, resets cursor, and supports next/previous pagination', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('input[name="province"]').setValue('广东')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(fetchSchools).toHaveBeenLastCalledWith(
      { schoolName: '', province: '广东', level: '' }, null, 10, expect.any(AbortSignal),
    )
    await wrapper.get('button[type="button"]:last-child').trigger('click')
    await flushPromises()
    expect(fetchSchools).toHaveBeenLastCalledWith(
      { schoolName: '', province: '广东', level: '' }, '2', 10, expect.any(AbortSignal),
    )
    wrapper.unmount()
  })

  it('shows an error and no fabricated records on API failure', async () => {
    vi.mocked(fetchSchools).mockRejectedValue(new Error('HTTP 503'))
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('HTTP 503')
    expect(wrapper.text()).not.toContain('演示大学')
    wrapper.unmount()
  })
})
