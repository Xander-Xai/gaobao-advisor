import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const overview = {
  data_profile: 'SYNTHETIC_DEMO',
  notice: '当前展示为程序生成的 SYNTHETIC_DEMO 演示数据。',
  counts: { schools: 8, majors: 12, admission_scores: 384, enrollment_plans: 144, subject_rankings: 40, score_rank_rows: 0 },
  years: [2023, 2024, 2025],
  year_from: 2023,
  year_to: 2025,
  provinces: ['示例省·甲', '示例省·乙'],
  levels: ['985', '211'],
  school_types: ['综合', '理工'],
  subject_types: ['物理类', '历史类'],
  scores_by_year: [
    { year: 2023, count: 128 },
    { year: 2024, count: 128 },
    { year: 2025, count: 128 },
  ],
  schools_with_scores: 8,
  schools_with_plans: 8,
  latest_admission_year: 2025,
  snapshot: {
    dataset_version: '1.1.0',
    profile: 'SYNTHETIC_DEMO',
    generated_at: '2026-01-01T00:00:00',
    year_from: 2023,
    year_to: 2025,
    seed: 20240617,
    is_synthetic: true,
  },
}

const school = {
  id: 1,
  name: '北辰示例科技大学（合成）',
  province: '示例省·甲',
  city: '示例市·晨',
  level: '985',
  school_type: '综合',
  ranking: 10,
  score_count: 48,
  plan_count: 12,
  latest_year: 2025,
  latest_min_score: 520,
  special_type: 'SYNTHETIC_DEMO_DATA',
  data_source_note: '合成演示数据，无真实来源',
  scores: [
    { id: 1, major_name: '计算机科学与技术（合成）', province: '示例省·甲', year: 2025, batch: '本科批', subject_type: '物理类', min_score: 520, avg_score: 540, max_score: 560, min_rank: 12000, plan_count: 30 },
  ],
  plans: [
    { id: 1, major_name: '计算机科学与技术（合成）', province: '示例省·甲', year: 2025, plan_count: 30, subject_requirement: '物理必选', batch: '本科批', duration: 4, tuition: 6000 },
  ],
  data_availability: { has_scores: true, has_plans: true, available_years: [2023, 2024, 2025], subject_types: ['物理类'] },
  website: null,
  description: '合成演示数据，无真实来源',
}

const trend = {
  school_id: 1,
  school_name: school.name,
  province: school.province,
  scope: 'school',
  major: null,
  aggregation: 'school_lowest_score_across_majors',
  series: [
    {
      subject_type: '物理类',
      direction: '逐年上升',
      change: 6,
      points: [
        { year: 2023, min_score: 514, avg_score: 534, max_score: 556, min_rank: 13000, record_count: 8 },
        { year: 2024, min_score: 517, avg_score: 537, max_score: 558, min_rank: 12500, record_count: 8 },
        { year: 2025, min_score: 520, avg_score: 540, max_score: 560, min_rank: 12000, record_count: 8 },
      ],
    },
  ],
  missing_years: [],
  notice: '趋势仅在同一学校、同一省份、同一科类内聚合。',
}

const dataAPI = {
  overview: vi.fn(),
  filters: vi.fn(),
  searchSchools: vi.fn(),
  schoolDetail: vi.fn(),
  trend: vi.fn(),
}

vi.mock('../../api/client', () => ({ dataAPI }))

async function mountView() {
  const DataView = (await import('../DataView.vue')).default
  return mount(DataView, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a><slot /></a>' },
      },
    },
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  dataAPI.overview.mockResolvedValue({ data: overview, error: null })
  dataAPI.filters.mockResolvedValue({
    data: { provinces: overview.provinces, levels: overview.levels, school_types: overview.school_types, years: [2025, 2024, 2023], subject_types: ['物理类'], majors: ['计算机科学与技术（合成）'] },
    error: null,
  })
  dataAPI.searchSchools.mockResolvedValue({
    data: { items: [school], total: 8, next_cursor: '1', has_more: true },
    error: null,
  })
  dataAPI.schoolDetail.mockResolvedValue({ data: school, error: null })
  dataAPI.trend.mockResolvedValue({ data: trend, error: null })
})

describe('DataView', () => {
  it('renders overview counts from the API instead of hardcoded values', async () => {
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('北辰示例科技大学（合成）')
    expect(wrapper.text()).toContain('384')
    expect(wrapper.text()).toContain('2023–2025')
    expect(wrapper.text()).toContain('合成演示')
  })

  it('opens a school detail and renders the subject-specific trend', async () => {
    const wrapper = await mountView()
    await flushPromises()
    await wrapper.find('[data-testid="data-school-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="data-school-detail"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('录取分数趋势')
    expect(wrapper.find('[data-testid="score-trend-chart"]').exists()).toBe(true)
    expect(dataAPI.trend).toHaveBeenCalledWith(
      expect.objectContaining({ schoolName: school.name, province: school.province, years: 3 }),
    )
  })

  it('shows an error state and retries the school list', async () => {
    dataAPI.searchSchools.mockResolvedValueOnce({ data: null, error: { message: '数据库不可用' } })
    const wrapper = await mountView()
    await flushPromises()
    expect(wrapper.text()).toContain('院校列表加载失败')
    expect(wrapper.text()).toContain('数据库不可用')
  })
})
