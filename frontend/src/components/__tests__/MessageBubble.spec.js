import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../chat/MessageBubble.vue'

describe('MessageBubble', () => {
  it('renders user message correctly', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          role: 'user',
          content: 'Hello world',
        },
      },
    })
    expect(wrapper.text()).toContain('Hello world')
    expect(wrapper.find('.bg-blue-600').exists()).toBe(true)
  })

  it('renders assistant message correctly', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          role: 'assistant',
          content: '**Bold** text',
        },
      },
    })
    expect(wrapper.text()).toContain('Bold text')
    expect(wrapper.find('.bg-white').exists()).toBe(true)
  })

  it('sanitizes XSS payload in content', () => {
    const xssPayload = '<script>alert("xss")</script><b>safe</b>'
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          role: 'assistant',
          content: xssPayload,
        },
      },
    })
    const html = wrapper.html()
    // XSS is prevented via HTML encoding + DOMPurify:
    // 1. < > chars are encoded BEFORE markdown rendering
    // 2. DOMPurify strips remaining dangerous tags
    expect(html).not.toContain('<script>')            // no raw <script> tag
    expect(html).toContain('alert("xss")')            // "alert" is safely HTML-encoded text, not executable
    expect(html).toContain('safe')                    // text content preserved
  })
})
