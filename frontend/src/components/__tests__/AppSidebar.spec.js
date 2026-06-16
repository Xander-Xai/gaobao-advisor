import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSidebar from '../AppSidebar.vue'

describe('AppSidebar', () => {
  it('renders sidebar navigation', () => {
    const wrapper = mount(AppSidebar)
    expect(wrapper.find('.sidebar').exists()).toBe(true)
  })

  it('displays scene selection buttons', () => {
    const wrapper = mount(AppSidebar)
    const buttons = wrapper.findAll('.scene-button')
    expect(buttons.length).toBeGreaterThanOrEqual(3) // gaokao, kaoyan, career
  })

  it('emits scene change event on button click', async () => {
    const wrapper = mount(AppSidebar)
    const buttons = wrapper.findAll('.scene-button')
    
    if (buttons.length > 0) {
      await buttons[0].trigger('click')
      expect(wrapper.emitted('scene-change')).toBeTruthy()
    }
  })

  it('highlights active scene', async () => {
    const wrapper = mount(AppSidebar, {
      props: {
        currentScene: 'gaokao'
      }
    })
    
    const activeButton = wrapper.find('.scene-button.active')
    expect(activeButton.exists()).toBe(true)
  })

  it('shows user profile summary when available', () => {
    const profile = {
      province: '山东',
      score: 580,
      subject: '物理类'
    }
    const wrapper = mount(AppSidebar, {
      props: {
        userProfile: profile
      }
    })
    
    expect(wrapper.find('.profile-summary').exists()).toBe(true)
  })

  it('displays new chat button', () => {
    const wrapper = mount(AppSidebar)
    expect(wrapper.find('.new-chat-button').exists()).toBe(true)
  })

  it('emits new chat event on button click', async () => {
    const wrapper = mount(AppSidebar)
    const button = wrapper.find('.new-chat-button')
    await button.trigger('click')
    
    expect(wrapper.emitted('new-chat')).toBeTruthy()
  })
})
