import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../chat/MessageBubble.vue'
import { feedbackAPI, highlightAPI } from '../../api/client'

vi.mock('../../api/client', () => ({
  feedbackAPI: { submit: vi.fn().mockResolvedValue({ data: { success: true }, error: null }) },
  highlightAPI: { submit: vi.fn().mockResolvedValue({ data: { success: true }, error: null }) },
}))

function assistantMessage(overrides = {}) {
  return {
    role: 'assistant',
    content: '这是一段足够长的合成回答内容，用于验证会话凭据透传。',
    messageIndex: 1,
    sessionId: 'session-owner',
    sessionToken: 'tok-owner',
    ...overrides,
  }
}

describe('MessageBubble auth propagation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends the session id and token when submitting feedback', async () => {
    const wrapper = mount(MessageBubble, { props: { message: assistantMessage() } })
    await wrapper.findAll('button')[0].trigger('click')
    expect(feedbackAPI.submit).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: 'session-owner', token: 'tok-owner' })
    )
  })

  it('sends the session id and token when saving a highlight', async () => {
    const wrapper = mount(MessageBubble, { props: { message: assistantMessage() } })
    await wrapper.findAll('button')[2].trigger('click')
    expect(highlightAPI.submit).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: 'session-owner', token: 'tok-owner' })
    )
  })
})
