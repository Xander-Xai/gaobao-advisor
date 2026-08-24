/**
 * Unified API client — one namespace per backend route module.
 *
 * Each non-streaming method returns a `{ data, error }` envelope. Chat uses a
 * streaming reader, while session-scoped mutations send the session Bearer
 * token issued by the backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

// ── Low-level helpers ────────────────────────────────────────────────

async function _request(path, { method = 'GET', body, headers = {}, token } = {}) {
  const finalHeaders = { 'Content-Type': 'application/json', ...headers }
  if (token) finalHeaders['Authorization'] = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (networkError) {
    return { data: null, error: { code: 'NETWORK_ERROR', message: networkError.message } }
  }

  let payload = null
  const text = await response.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { raw: text }
    }
  }

  if (!response.ok) {
    return {
      data: null,
      error: {
        code: payload?.code || `HTTP_${response.status}`,
        message: payload?.detail || payload?.error || payload?.message || response.statusText,
        status: response.status,
      },
    }
  }
  return { data: payload, error: null }
}

function _toQuery(params) {
  if (!params) return ''
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === '') continue
    usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

// ── chat (SSE — special-cased; the helper above cannot read a stream) ─

export const chatAPI = {
  async createSession(scene = 'gaokao') {
    return _request('/session', { method: 'POST', body: { scene } })
  },

  /**
   * Send a chat message and consume SSE events as they arrive.
   * The session token must match sessionId; `onEvent` receives each parsed
   * event immediately while the full event list is still returned at EOF.
   */
  async send(sessionId, message, slots = {}, scene = 'gaokao', onEvent = null, token = null) {
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`

    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ session_id: sessionId, message, slots, scene }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`Chat failed: HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const events = []
    let buffer = ''

    const consumeLines = (text, flush = false) => {
      buffer += text
      const lines = buffer.split('\n')
      buffer = flush ? '' : (lines.pop() || '')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          events.push(event)
          if (onEvent) onEvent(event)
        } catch {
          // Ignore malformed SSE data lines.
        }
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      consumeLines(decoder.decode(value, { stream: true }))
    }
    consumeLines(decoder.decode(), true)

    return events
  },
}

// ── onboarding ──────────────────────────────────────────────────────

export const onboardingAPI = {
  async step(stepNum, data) {
    return _request('/onboarding', { method: 'POST', body: { step: stepNum, data } })
  },
}

// ── chat metadata (feedback + highlight) ────────────────────────────

export const feedbackAPI = {
  async submit({ sessionId, messageIndex, rating, feedbackText, qualityScoreId, token }) {
    return _request('/chat/feedback', {
      method: 'POST',
      token,
      body: {
        session_id: sessionId,
        message_index: messageIndex,
        rating,
        feedback_text: feedbackText,
        quality_score_id: qualityScoreId,
      },
    })
  },
}

export const highlightAPI = {
  async submit({ sessionId, content, score = 80, token }) {
    return _request('/chat/highlight', {
      method: 'POST',
      token,
      body: { session_id: sessionId, content, score },
    })
  },
}

// ── data — schools / scores / plans ─────────────────────────────────

export const dataAPI = {
  async searchSchools({ schoolName, province, level, limit = 50, cursor } = {}) {
    const qs = _toQuery({
      school_name: schoolName,
      province,
      level,
      limit,
      cursor,
    })
    return _request(`/data/schools${qs}`)
  },

  async getScores({ schoolName, province, year, major, limit = 50, cursor }) {
    const qs = _toQuery({
      school_name: schoolName,
      province,
      year,
      major,
      limit,
      cursor,
    })
    return _request(`/data/scores${qs}`)
  },

  async getPlans({ schoolName, province, year, limit = 50, cursor }) {
    const qs = _toQuery({
      school_name: schoolName,
      province,
      year,
      limit,
      cursor,
    })
    return _request(`/data/plans${qs}`)
  },
}

// ── knowledge — RAG search + quotes ─────────────────────────────────

export const knowledgeAPI = {
  async search({ query, groups, topK = 5 }) {
    return _request('/knowledge/search', {
      method: 'POST',
      body: { query, groups, top_k: topK },
    })
  },
  async getQuotes({ major, topK = 5 }) {
    const qs = _toQuery({ major, top_k: topK })
    return _request(`/knowledge/quotes${qs}`)
  },
}

// ── profile — requires Bearer token ─────────────────────────────────

export const profileAPI = {
  async get(sessionId, token) {
    return _request(`/profile/${encodeURIComponent(sessionId)}`, { token })
  },
  async update(sessionId, { field, value }, token) {
    return _request(`/profile/${encodeURIComponent(sessionId)}`, {
      method: 'PUT',
      body: { field, value },
      token,
    })
  },
  async nextQuestion(sessionId, token) {
    return _request(`/profile/${encodeURIComponent(sessionId)}/next-question`, { token })
  },
  async skip(sessionId, { field }, token) {
    return _request(`/profile/${encodeURIComponent(sessionId)}/skip`, {
      method: 'POST',
      body: { field },
      token,
    })
  },
}

// ── report — generate / fetch / export ──────────────────────────────

export const reportAPI = {
  async generate({ sessionId, studentName } = {}) {
    return _request('/report/generate', {
      method: 'POST',
      body: { session_id: sessionId, student_name: studentName },
    })
  },
  async fetch(reportId) {
    return _request(`/report/${encodeURIComponent(reportId)}`)
  },
  exportHTML(reportId) {
    window.open(`${API_BASE}/report/${encodeURIComponent(reportId)}/html`, '_blank')
  },
  exportCover(reportId) {
    window.open(`${API_BASE}/report/${encodeURIComponent(reportId)}/cover.svg`, '_blank')
  },
}

// ── health ──────────────────────────────────────────────────────────

export const healthAPI = {
  async check() {
    return _request('/health')
  },
}
