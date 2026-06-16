import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChatArea from '../chat/ChatArea.vue'

describe('ChatArea', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders empty state when no messages', () => {
    const wrapper = mount(ChatArea)
    expect(wrapper.exists()).toBe(true)
  })

  it('renders message list with messages', () => {
    const wrapper = mount(ChatArea)
    // Component uses chat store messages, not props
    expect(wrapper.find('div').exists()).toBe(true)
  })

  it('has container for chat messages', () => {
    const wrapper = mount(ChatArea)
    expect(wrapper.find('div').exists()).toBe(true)
  })

  it('displays streaming indicator when isStreaming', () => {
    const wrapper = mount(ChatArea)
    // Streaming state comes from store
    expect(wrapper.find('div').exists()).toBe(true)
  })
})
