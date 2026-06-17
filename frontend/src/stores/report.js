import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { reportAPI } from '../api/client'

/**
 * Report store — delegates to the unified API client.
 *
 * Note: `generateReport` / `fetchReport` retain their original signatures
 * (returning the data directly) so existing callers like ReportView keep
 * working unchanged. Internally we still surface errors via the `error`
 * ref for the loading/error UI to display.
 */
export const useReportStore = defineStore('report', () => {
  const report = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const hasReport = computed(() => !!report.value)

  async function generateReport(sessionId, studentName = '') {
    loading.value = true
    error.value = null
    const { data, error: err } = await reportAPI.generate({ sessionId, studentName })
    loading.value = false
    if (err) {
      error.value = err.message || '生成失败'
      throw new Error(error.value)
    }
    // Backend's GenerateResponse contains { report_id, status, message }.
    // Preserve previous behaviour: store the envelope so the view can read
    // report_id; ReportView reads from store.report via fetchReport anyway.
    report.value = data
    return data
  }

  async function fetchReport(reportId) {
    loading.value = true
    error.value = null
    const { data, error: err } = await reportAPI.fetch(reportId)
    loading.value = false
    if (err) {
      error.value = err.message || '获取失败'
      throw new Error(error.value)
    }
    report.value = data
    return data
  }

  function exportHTML(reportId) {
    reportAPI.exportHTML(reportId)
  }

  function exportCover(reportId) {
    reportAPI.exportCover(reportId)
  }

  return { report, loading, error, hasReport, generateReport, fetchReport, exportHTML, exportCover }
})
