import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppHeader from '../layout/AppHeader.vue'

describe('AppHeader', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders header with scene buttons', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.find('div').exists()).toBe(true)
    // Should contain scene buttons
    expect(wrapper.findAll('button').length).toBeGreaterThan(0)
  })

  it('displays scene labels', () => {
    const wrapper = mount(AppHeader)
    const text = wrapper.text()
    expect(text.length).toBeGreaterThan(0)
  })

  it('has interactive buttons', () => {
    const wrapper = mount(AppHeader)
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBeGreaterThanOrEqual(3)
  })
})
