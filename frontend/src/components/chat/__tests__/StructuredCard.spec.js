import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StructuredCard from '../StructuredCard.vue'

const card = {
  title: '高考志愿规划建议',
  summary: '河北 620 分，意向计算机',
  facts: ['省份：河北', '分数：620'],
  suggestions: ['推荐：北辰示例科技大学（合成），参考线600分'],
  risks: ['数据有限，建议以官方最新信息为准'],
  next_actions: ['核对招生计划'],
  sources: ['数据库位次法（合成）'],
  confidence: 0.86,
}

describe('StructuredCard', () => {
  it('renders every recommendation section', () => {
    const wrapper = mount(StructuredCard, { props: { card } })

    expect(wrapper.get('[data-testid="structured-card"]').exists()).toBe(true)
    expect(wrapper.text()).toContain(card.title)
    expect(wrapper.text()).toContain('北辰示例科技大学')
    expect(wrapper.get('[data-testid="structured-facts"]').text()).toContain('省份：河北')
    expect(wrapper.get('[data-testid="structured-risks"]').text()).toContain('数据有限')
    expect(wrapper.get('[data-testid="structured-next-actions"]').text()).toContain('核对招生计划')
    expect(wrapper.get('[data-testid="structured-sources"]').text()).toContain('数据库位次法')
    expect(wrapper.get('[data-testid="structured-confidence"]').text()).toContain('86%')
  })

  it('escapes untrusted slot text instead of rendering markup', () => {
    const wrapper = mount(StructuredCard, {
      props: {
        card: {
          ...card,
          facts: ['<img src=x onerror=alert(1)>'],
        },
      },
    })
    expect(wrapper.html()).not.toContain('<img')
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })

  it('omits empty sections', () => {
    const wrapper = mount(StructuredCard, {
      props: { card: { title: '规划建议', summary: '等待更多信息' } },
    })
    expect(wrapper.find('[data-testid="structured-facts"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="structured-sources"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="structured-confidence"]').exists()).toBe(false)
  })
})
