import { describe, it, expect } from 'vitest'
import { sanitizeHtml, renderMarkdown } from '../../utils/sanitize'

describe('sanitizeHtml', () => {
  it('returns empty string for falsy input', () => {
    expect(sanitizeHtml('')).toBe('')
    expect(sanitizeHtml(null)).toBe('')
    expect(sanitizeHtml(undefined)).toBe('')
  })

  it('allows safe formatting tags', () => {
    const input = '<p>Hello <strong>world</strong></p>'
    expect(sanitizeHtml(input)).toContain('<p>')
    expect(sanitizeHtml(input)).toContain('<strong>')
  })

  it('removes dangerous tags', () => {
    const input = '<script>alert("xss")</script><p>safe</p>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('<script>')
    expect(result).not.toContain('alert')
    expect(result).toContain('<p>')
  })

  it('removes event handlers', () => {
    const input = '<p onclick="alert(1)">click me</p>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('onclick')
  })

  it('removes data attributes', () => {
    const input = '<p data-x="evil">text</p>'
    const result = sanitizeHtml(input)
    expect(result).not.toContain('data-x')
  })
})

describe('renderMarkdown', () => {
  it('converts bold markdown to strong tags', () => {
    const result = renderMarkdown('**bold**')
    expect(result).toContain('<strong>bold</strong>')
  })

  it('converts newlines to br tags', () => {
    const result = renderMarkdown('line1\nline2')
    expect(result).toContain('<br>')
  })

  it('escapes HTML entities before markdown conversion', () => {
    const result = renderMarkdown('<script>alert(1)</script>')
    expect(result).not.toContain('<script>')
  })

  it('sanitizes output after markdown conversion', () => {
    const result = renderMarkdown('**bold** <script>alert(1)</script>')
    expect(result).toContain('<strong>bold</strong>')
    expect(result).not.toContain('<script>')
  })
})
