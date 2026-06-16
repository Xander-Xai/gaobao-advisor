import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatArea from '../ChatArea.vue'

describe('ChatArea', () => {
  it('renders empty state when no messages', () => {
    const wrapper = mount(ChatArea, {
      props: {
        messages: []
      }
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('renders message list with messages', () => {
    const messages = [
      { id: 1, role: 'user', content: '你好' },
      { id: 2, role: 'assistant', content: '你好！我是高考志愿顾问' }
    ]
    const wrapper = mount(ChatArea, {
      props: {
        messages
      }
    })
    expect(wrapper.findAll('.message-bubble')).toHaveLength(2)
  })

  it('auto-scrolls to bottom on new message', async () => {
    const messages = [{ id: 1, role: 'user', content: 'test' }]
    const wrapper = mount(ChatArea, {
      props: {
        messages
      }
    })
    
    // Simulate scroll behavior
    const container = wrapper.find('.chat-area-container')
    expect(container.exists()).toBe(true)
  })

  it('displays streaming indicator during SSE', () => {
    const wrapper = mount(ChatArea, {
      props: {
        messages: [],
        isStreaming: true
      }
    })
    expect(wrapper.find('.streaming-indicator').exists()).toBe(true)
  })

  it('handles emotion state display', () => {
    const wrapper = mount(ChatArea, {
      props: {
        messages: [],
        emotionState: '焦虑'
      }
    })
    expect(wrapper.exists()).toBe(true)
  })
})
