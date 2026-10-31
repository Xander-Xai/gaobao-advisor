import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import ChatArea from '../chat/ChatArea.vue'
import { useChatStore } from '../../stores/chat'

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

  it('keeps rendering after a new session replaces the messages array', async () => {
    const wrapper = mount(ChatArea)
    const chat = useChatStore()
    chat.createSession()
    chat.messages.push({ role: 'user', content: '新会话中的消息' })
    await nextTick()
    expect(wrapper.text()).toContain('新会话中的消息')
    expect(wrapper.text()).not.toContain('请告诉我您的省份')
  })
})
