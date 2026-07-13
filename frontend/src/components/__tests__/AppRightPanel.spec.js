import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppRightPanel from '../layout/AppRightPanel.vue'

describe('AppRightPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders right panel with title', () => {
    const wrapper = mount(AppRightPanel)
    expect(wrapper.text()).toContain('考生画像')
  })

  it('displays empty state when no slots', () => {
    const wrapper = mount(AppRightPanel)
    expect(wrapper.text()).toContain('对话后将显示考生画像')
  })

  it('renders panel container', () => {
    const wrapper = mount(AppRightPanel)
    expect(wrapper.find('div').exists()).toBe(true)
  })
})