import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageInput from '../MessageInput.vue'

describe('MessageInput', () => {
  it('renders input field and send button', () => {
    const wrapper = mount(MessageInput)
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('emits send event on button click', async () => {
    const wrapper = mount(MessageInput)
    const input = wrapper.find('input')
    await input.setValue('测试消息')
    
    const button = wrapper.find('button')
    await button.trigger('click')
    
    expect(wrapper.emitted('send')).toBeTruthy()
    expect(wrapper.emitted('send')[0]).toEqual(['测试消息'])
  })

  it('emits send event on Enter key', async () => {
    const wrapper = mount(MessageInput)
    const input = wrapper.find('input')
    await input.setValue('测试消息')
    await input.trigger('keyup', { key: 'Enter' })
    
    expect(wrapper.emitted('send')).toBeTruthy()
  })

  it('disables send button when input is empty', () => {
    const wrapper = mount(MessageInput, {
      props: {
        disabled: true
      }
    })
    const button = wrapper.find('button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('clears input after sending', async () => {
    const wrapper = mount(MessageInput)
    const input = wrapper.find('input')
    await input.setValue('测试消息')
    
    const button = wrapper.find('button')
    await button.trigger('click')
    
    expect(input.element.value).toBe('')
  })

  it('respects max length limit', async () => {
    const wrapper = mount(MessageInput)
    const input = wrapper.find('input')
    const longText = 'a'.repeat(3001)
    await input.setValue(longText)
    
    // Input should be truncated to 3000 chars
    expect(input.element.value.length).toBeLessThanOrEqual(3000)
  })

  it('shows character count near limit', async () => {
    const wrapper = mount(MessageInput)
    const input = wrapper.find('input')
    await input.setValue('a'.repeat(2900))
    
    expect(wrapper.find('.char-count').exists()).toBe(true)
  })
})
