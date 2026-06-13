export const chatAPI = {
  async send(sessionId, message, slots = {}) {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, slots, scene: 'gaokao' }),
    })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    const events = []
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const text = decoder.decode(value)
      const lines = text.split('\n').filter(l => l.startsWith('data: '))
      for (const line of lines) {
        try { events.push(JSON.parse(line.slice(6))) } catch {}
      }
    }
    return events
  },
}

export const onboardingAPI = {
  async step(stepNum, data) {
    const res = await fetch('/api/v1/onboarding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ step: stepNum, data }),
    })
    return res.json()
  },
}
