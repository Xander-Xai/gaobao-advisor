import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppHeader from '../AppHeader.vue'

describe('AppHeader', () => {
  it('renders header with title', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.find('.app-header').exists()).toBe(true)
    expect(wrapper.text()).toContain('高考志愿顾问')
  })

  it('displays connection status indicator', () => {
    const wrapper = mount(AppHeader, {
      props: {
        isConnected: true
      }
    })
    
    expect(wrapper.find('.status-indicator').exists()).toBe(true)
  })

  it('shows online status when connected', () => {
    const wrapper = mount(AppHeader, {
      props: {
        isConnected: true
      }
    })
    
    const status = wrapper.find('.status-indicator')
    expect(status.classes()).toContain('online')
  })

  it('shows offline status when disconnected', () => {
    const wrapper = mount(AppHeader, {
      props: {
        isConnected: false
      }
    })
    
    const status = wrapper.find('.status-indicator')
    expect(status.classes()).toContain('offline')
  })

  it('displays voice call button', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.find('.voice-button').exists()).toBe(true)
  })

  it('emits voice call event on button click', async () => {
    const wrapper = mount(AppHeader)
    const button = wrapper.find('.voice-button')
    await button.trigger('click')
    
    expect(wrapper.emitted('voice-call')).toBeTruthy()
  })

  it('shows settings menu toggle', () => {
    const wrapper = mount(AppHeader)
    expect(wrapper.find('.settings-toggle').exists()).toBe(true)
  })
})
