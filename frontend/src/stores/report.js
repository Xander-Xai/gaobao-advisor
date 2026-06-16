import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const useReportStore = defineStore('report', () => {
  const report = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const hasReport = computed(() => !!report.value)

  async function generateReport(sessionId, studentName = '') {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/report/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, student_name: studentName })
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || '生成失败')
      report.value = data
      return data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchReport(reportId) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/report/${reportId}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || '获取失败')
      report.value = data
      return data
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  function exportHTML(reportId) {
    window.open(`${API_BASE}/report/${reportId}/html`, '_blank')
  }

  function exportCover(reportId) {
    window.open(`${API_BASE}/report/${reportId}/cover.svg`, '_blank')
  }

  return { report, loading, error, hasReport, generateReport, fetchReport, exportHTML, exportCover }
})