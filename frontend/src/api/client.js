/**
 * Unified API client — one namespace per backend route module.
 *
 * Each non-streaming method returns a `{ data, error }` envelope (per
 * common/patterns.md). Network/parse failures populate `error`;
 * HTTP 2xx populates `data`; HTTP 4xx/5xx populates `error` with the
 * server's detail when present.
 *
 * Auth: profile endpoints require `Authorization: Bearer <session_token>`.
 * The token is received in the chat SSE `done` event and stored in
 * the chat store. Callers pass the token explicitly (avoids circular
 * import between this client and the Pinia store).
 */

export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

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

  // Try to parse JSON regardless of status — FastAPI always returns JSON.
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
  /**
   * Send a chat message and yield SSE events one by one.
   * Returns the list of parsed JSON events collected from the stream.
   * Caller must read the final `done.session_token` to auth profile/voice.
   */
  async send(sessionId, message, slots = {}, scene = 'gaokao', onEvent) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, slots, scene }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`Chat failed: HTTP ${response.status}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const events = []
    let buffer = ''

    function handleLine(line) {
      if (!line.startsWith('data: ')) return
      try {
        const event = JSON.parse(line.slice(6))
        events.push(event)
        if (onEvent) onEvent(event)
      } catch {
        // Ignore malformed lines — server may emit heartbeat separators.
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        handleLine(line)
      }
    }
    buffer += decoder.decode()
    if (buffer) handleLine(buffer)
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
      body: {
        session_id: sessionId,
        message_index: messageIndex,
        rating,
        feedback_text: feedbackText,
        quality_score_id: qualityScoreId,
      },
      token,
    })
  },
}

export const highlightAPI = {
  /**
   * Submit a highlight (金句) extracted from an assistant reply.
   * `score` defaults to 80; UI may allow the user to adjust later.
   * `token` is the HMAC session token from chat SSE done event.
   */
  async submit({ sessionId, content, score = 80, token }) {
    return _request('/chat/highlight', {
      method: 'POST',
      body: { session_id: sessionId, content, score },
      token,
    })
  },
}

// ── data — schools / scores / plans ─────────────────────────────────

export const dataAPI = {
  /**
   * Search schools. Returns either `{count, results}` (school_name mode,
   * FTS-based single match) or `{items, next_cursor, has_more}` (cursor
   * pagination when listing by province/level).
   */
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

  /** Admission scores for a school in a province. */
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

  /** Enrollment plans for a school. */
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

// ── profile — requires Bearer token from chat SSE `done` event ─────

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
  async generate({ sessionId, studentName, token } = {}) {
    return _request('/report/generate', {
      method: 'POST',
      body: { session_id: sessionId, student_name: studentName, token },
    })
  },
  authQuery({ sessionId, token } = {}) {
    return _toQuery({ session_id: sessionId, token })
  },
  async fetch(reportId, auth = {}) {
    return _request(`/report/${encodeURIComponent(reportId)}${this.authQuery(auth)}`)
  },
  htmlURL(reportId, auth = {}) {
    return `${API_BASE}/report/${encodeURIComponent(reportId)}/html${this.authQuery(auth)}`
  },
  coverURL(reportId, auth = {}) {
    return `${API_BASE}/report/${encodeURIComponent(reportId)}/cover.svg${this.authQuery(auth)}`
  },
  exportHTML(reportId, auth = {}) {
    window.open(this.htmlURL(reportId, auth), '_blank')
  },
  exportCover(reportId, auth = {}) {
    window.open(this.coverURL(reportId, auth), '_blank')
  },
}

// ── health ──────────────────────────────────────────────────────────

export const healthAPI = {
  async check() {
    return _request('/health')
  },
}
