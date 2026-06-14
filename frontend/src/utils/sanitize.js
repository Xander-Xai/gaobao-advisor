/**
 * HTML sanitization utility — wraps DOMPurify to safely render
 * AI-generated markdown content without XSS vectors.
 */
import DOMPurify from 'dompurify'

/**
 * Sanitize HTML string, stripping all dangerous elements while
 * keeping safe formatting tags.
 * @param {string} html - Raw HTML string (e.g., from markdown conversion)
 * @returns {string} Sanitized HTML safe for v-html rendering
 */
export function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['strong', 'em', 'br', 'p', 'ul', 'ol', 'li', 'a', 'code', 'pre', 'blockquote'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
    ALLOW_DATA_ATTR: false,
  })
}

/**
 * Convert simple markdown to HTML and sanitize.
 * Handles: **bold**, newlines → <br>
 * @param {string} text - Raw text with markdown
 * @returns {string} Sanitized HTML
 */
export function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  return sanitizeHtml(html)
}
