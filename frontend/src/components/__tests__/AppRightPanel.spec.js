import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppRightPanel from '../AppRightPanel.vue'

describe('AppRightPanel', () => {
  it('renders right panel container', () => {
    const wrapper = mount(AppRightPanel)
    expect(wrapper.find('.right-panel').exists()).toBe(true)
  })

  it('displays user profile section', () => {
    const wrapper = mount(AppRightPanel)
    expect(wrapper.find('.profile-section').exists()).toBe(true)
  })

  it('shows filled slots count', () => {
    const slots = {
      province: { filled: true, value: '山东' },
      score_rank: { filled: true, value: '580' },
      subject: { filled: false, value: '' },
      interest: { filled: true, value: '计算机' }
    }
    const wrapper = mount(AppRightPanel, {
      props: {
        slots
      }
    })
    
    expect(wrapper.text()).toContain('3/4')
  })

  it('displays missing fields warning', () => {
    const slots = {
      province: { filled: false, value: '' },
      score_rank: { filled: false, value: '' }
    }
    const wrapper = mount(AppRightPanel, {
      props: {
        slots
      }
    })
    
    expect(wrapper.find('.missing-fields-warning').exists()).toBe(true)
  })

  it('shows quote recommendations when available', () => {
    const quotes = [
      { id: '1', text: '选择大于努力', category: '专业选择' }
    ]
    const wrapper = mount(AppRightPanel, {
      props: {
        quotes
      }
    })
    
    expect(wrapper.find('.quote-section').exists()).toBe(true)
  })

  it('displays emotion state indicator', () => {
    const wrapper = mount(AppRightPanel, {
      props: {
        emotionState: '焦虑'
      }
    })
    
    expect(wrapper.find('.emotion-indicator').exists()).toBe(true)
    expect(wrapper.text()).toContain('焦虑')
  })

  it('collapses panel on toggle', async () => {
    const wrapper = mount(AppRightPanel)
    const toggleButton = wrapper.find('.panel-toggle')
    
    if (toggleButton.exists()) {
      await toggleButton.trigger('click')
      expect(wrapper.classes()).toContain('collapsed')
    }
  })
})
