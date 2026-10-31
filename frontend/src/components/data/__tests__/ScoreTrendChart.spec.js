import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ScoreTrendChart from '../ScoreTrendChart.vue'

const series = [
  {
    subject_type: '物理类',
    direction: '逐年上升',
    change: 6,
    points: [
      { year: 2023, min_score: 600, avg_score: 620, max_score: 640, min_rank: 12000, record_count: 2 },
      { year: 2024, min_score: 603, avg_score: 623, max_score: 641, min_rank: 11800, record_count: 2 },
      { year: 2025, min_score: 606, avg_score: 626, max_score: 645, min_rank: 11500, record_count: 2 },
    ],
  },
]

describe('ScoreTrendChart', () => {
  it('renders one labelled series without merging subjects', () => {
    const wrapper = mount(ScoreTrendChart, { props: { series } })
    expect(wrapper.find('[data-testid="score-trend-chart"]').exists()).toBe(true)
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.text()).toContain('物理类')
    expect(wrapper.text()).toContain('逐年上升')
    expect(wrapper.findAll('circle')).toHaveLength(3)
  })

  it('shows an empty state when no points exist', () => {
    const wrapper = mount(ScoreTrendChart, { props: { series: [] } })
    expect(wrapper.text()).toContain('暂无可绘制的趋势数据')
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('warns when only one year is available', () => {
    const wrapper = mount(ScoreTrendChart, {
      props: { series: [{ ...series[0], points: [series[0].points[0]] }] },
    })
    expect(wrapper.text()).toContain('无法判断趋势')
  })

  it('exposes a data table with provenance-friendly row counts', () => {
    const wrapper = mount(ScoreTrendChart, { props: { series } })
    expect(wrapper.find('details').text()).toContain('查看数据表')
    expect(wrapper.find('details').text()).toContain('记录数')
  })
})
