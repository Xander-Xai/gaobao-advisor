import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppSidebar from '../layout/AppSidebar.vue'

describe('AppSidebar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders sidebar with new chat button', () => {
    const wrapper = mount(AppSidebar)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('displays session list area', () => {
    const wrapper = mount(AppSidebar)
    expect(wrapper.find('div').exists()).toBe(true)
  })

  it('shows empty state when no sessions', () => {
    const wrapper = mount(AppSidebar)
    expect(wrapper.text()).toContain('点击上方按钮开始')
  })
})
