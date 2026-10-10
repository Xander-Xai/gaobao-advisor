import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { reportAPI } from '../api/client'
import { useChatStore } from './chat'

/**
 * Report store — delegates to the unified API client.
 *
 * Note: `generateReport` / `fetchReport` retain their original signatures
 * (returning the data directly) so existing callers like ReportView keep
 * working unchanged. Internally we still surface errors via the `error`
 * ref for the loading/error UI to display.
 */
export const useReportStore = defineStore('report', () => {
  const _generateResponse = ref(null)
  const reportData = ref(null)
  const loading = ref(false)
  const error = ref(null)

  /** Returns the full report data, or the generate-response envelope as fallback. */
  const report = computed(() => reportData.value || _generateResponse.value)
  const hasReport = computed(() => !!reportData.value)

  function currentAuth() {
    const chatStore = useChatStore()
    return {
      sessionId: chatStore.currentSessionId,
      token: chatStore.sessionToken,
    }
  }

  function requireReportAuth() {
    const auth = currentAuth()
    if (!auth.sessionId || !auth.token) {
      throw new Error('请先在对话页发送一条消息，获取会话授权后再操作报告')
    }
    return auth
  }

  async function generateReport(sessionId, studentName = '') {
    loading.value = true
    error.value = null
    let auth
    try {
      auth = requireReportAuth()
    } catch (authError) {
      loading.value = false
      error.value = authError.message
      throw authError
    }
    const { data, error: err } = await reportAPI.generate({ sessionId, studentName, token: auth.token })
    loading.value = false
    if (err) {
      error.value = err.message || '生成失败'
      throw new Error(error.value)
    }
    // Backend's GenerateResponse contains { report_id, status, message }.
    // Store the envelope separately; fetchReport populates reportData with
    // the full report JSON so the view never sees the intermediate envelope.
    _generateResponse.value = data
    return data
  }

  async function fetchReport(reportId) {
    loading.value = true
    error.value = null
    let auth
    try {
      auth = requireReportAuth()
    } catch (authError) {
      loading.value = false
      error.value = authError.message
      throw authError
    }
    const { data, error: err } = await reportAPI.fetch(reportId, auth)
    loading.value = false
    if (err) {
      error.value = err.message || '获取失败'
      throw new Error(error.value)
    }
    reportData.value = data
    return data
  }

  function exportHTML(reportId) {
    reportAPI.exportHTML(reportId, currentAuth())
  }

  function exportCover(reportId) {
    reportAPI.exportCover(reportId, currentAuth())
  }

  function coverURL(reportId) {
    return reportAPI.coverURL(reportId, currentAuth())
  }

  return { report, loading, error, hasReport, generateReport, fetchReport, exportHTML, exportCover, coverURL }
})
