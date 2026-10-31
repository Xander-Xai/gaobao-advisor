import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { AdminApiError, adminApi } from '../api/admin'
import type {
  AdminRole,
  AdminUser,
  AuditLog,
  FilterOptions,
  JobStatus,
  QualityJob,
  QualityJobDetail,
  SchoolDetail,
  SchoolListItem,
  Stats,
  SystemStatus,
} from '../types/admin'

const TOKEN_KEY = 'gaobao.admin.token'
const USER_KEY = 'gaobao.admin.user'
const PAGE_SIZE = 10

interface SchoolFilters {
  q: string
  province: string
  level: string
  sort: 'id' | 'name' | 'province' | 'level' | 'ranking' | 'score_count'
  order: 'asc' | 'desc'
}

interface JobFilters {
  status: JobStatus | ''
  review_status: '' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED'
}

function readSession<T>(key: string): T | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function readToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.sessionStorage.getItem(TOKEN_KEY)
}

function messageOf(error: unknown): string {
  if (error instanceof AdminApiError) return `${error.message}（${error.code}）`
  if (error instanceof Error) return error.message
  return '未知错误'
}

function idempotencyKey(): string {
  const value = globalThis.crypto?.randomUUID?.()
  return value ?? `job-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const useAdminStore = defineStore('admin', () => {
  const token = ref<string | null>(readToken())
  const user = ref<AdminUser | null>(readSession<AdminUser>(USER_KEY))
  const stats = ref<Stats | null>(null)
  const systemStatus = ref<SystemStatus | null>(null)
  const filterOptions = ref<FilterOptions>({ provinces: [], levels: [], school_types: [] })

  const filters = reactive<SchoolFilters>({ q: '', province: '', level: '', sort: 'id', order: 'asc' })
  const jobFilters = reactive<JobFilters>({ status: '', review_status: '' })

  const schools = ref<SchoolListItem[]>([])
  const schoolTotal = ref(0)
  const schoolPage = ref(1)
  const schoolPages = ref(0)
  const schoolsLoading = ref(false)
  const schoolsError = ref('')

  const selectedSchool = ref<SchoolDetail | null>(null)
  const schoolDetailId = ref<number | null>(null)
  const detailLoading = ref(false)
  const detailError = ref('')

  const jobs = ref<QualityJob[]>([])
  const jobsTotal = ref(0)
  const jobsPage = ref(1)
  const jobsPages = ref(0)
  const jobsLoading = ref(false)
  const jobsError = ref('')

  const selectedJob = ref<QualityJobDetail | null>(null)
  const jobDetailId = ref<number | null>(null)
  const jobDetailLoading = ref(false)
  const jobDetailError = ref('')

  const auditLogs = ref<AuditLog[]>([])
  const auditTotal = ref(0)
  const auditPage = ref(1)
  const auditPages = ref(0)
  const auditLoading = ref(false)
  const auditError = ref('')

  const actionPending = ref(false)
  const actionError = ref('')
  const notice = ref('')

  let pollTimer: number | null = null

  const isAuthenticated = computed(() => Boolean(token.value))
  const role = computed<AdminRole | null>(() => user.value?.role ?? null)
  const canWrite = computed(() => role.value === 'operator' || role.value === 'admin')
  const isAdmin = computed(() => role.value === 'admin')

  function persist(): void {
    if (typeof window === 'undefined') return
    if (token.value) window.sessionStorage.setItem(TOKEN_KEY, token.value)
    else window.sessionStorage.removeItem(TOKEN_KEY)
    if (user.value) window.sessionStorage.setItem(USER_KEY, JSON.stringify(user.value))
    else window.sessionStorage.removeItem(USER_KEY)
  }

  function clearData(): void {
    stats.value = null
    systemStatus.value = null
    filterOptions.value = { provinces: [], levels: [], school_types: [] }
    schools.value = []
    selectedSchool.value = null
    schoolDetailId.value = null
    jobs.value = []
    selectedJob.value = null
    jobDetailId.value = null
    auditLogs.value = []
    schoolsError.value = ''
    jobsError.value = ''
    auditError.value = ''
    detailError.value = ''
    actionError.value = ''
    notice.value = ''
  }

  async function logout(): Promise<void> {
    const currentToken = token.value
    let warning = ''
    if (currentToken) {
      try {
        await adminApi.logout(currentToken)
      } catch (error) {
        if (!(error instanceof AdminApiError && error.status === 401)) {
          warning = '已退出本机，但服务端撤销未确认，请重新登录后检查会话状态'
        }
      }
    }
    stopPolling()
    token.value = null
    user.value = null
    persist()
    clearData()
    if (warning) actionError.value = warning
  }

  function handleAuthError(error: unknown): boolean {
    if (error instanceof AdminApiError && error.status === 401) {
      logout()
      actionError.value = '登录已过期，请重新登录'
      return true
    }
    return false
  }

  async function login(username: string, password: string): Promise<boolean> {
    actionPending.value = true
    actionError.value = ''
    notice.value = ''
    try {
      const response = await adminApi.login(username.trim(), password)
      token.value = response.access_token
      user.value = response.user
      persist()
      await refreshAll()
      return true
    } catch (error) {
      actionError.value = messageOf(error)
      return false
    } finally {
      actionPending.value = false
    }
  }

  async function loadStats(): Promise<void> {
    if (!token.value) return
    try {
      stats.value = await adminApi.stats(token.value)
    } catch (error) {
      if (!handleAuthError(error)) actionError.value = messageOf(error)
    }
  }

  async function loadSystemStatus(): Promise<void> {
    if (!token.value) return
    try {
      systemStatus.value = await adminApi.systemStatus(token.value)
    } catch (error) {
      if (!handleAuthError(error)) actionError.value = messageOf(error)
    }
  }

  async function loadFilterOptions(): Promise<void> {
    if (!token.value) return
    try {
      filterOptions.value = await adminApi.filterOptions(token.value)
    } catch (error) {
      if (!handleAuthError(error)) actionError.value = messageOf(error)
    }
  }

  async function loadSchools(page = 1): Promise<void> {
    if (!token.value) return
    schoolsLoading.value = true
    schoolsError.value = ''
    try {
      const response = await adminApi.schools(
        {
          q: filters.q || undefined,
          province: filters.province || undefined,
          level: filters.level || undefined,
          sort: filters.sort,
          order: filters.order,
          page,
          page_size: PAGE_SIZE,
        },
        token.value,
      )
      schools.value = response.items
      schoolTotal.value = response.total
      schoolPage.value = response.page
      schoolPages.value = response.pages
    } catch (error) {
      if (!handleAuthError(error)) schoolsError.value = messageOf(error)
      schools.value = []
    } finally {
      schoolsLoading.value = false
    }
  }

  async function loadSchool(id: number): Promise<void> {
    if (!token.value) return
    schoolDetailId.value = id
    detailLoading.value = true
    detailError.value = ''
    try {
      selectedSchool.value = await adminApi.school(id, token.value)
    } catch (error) {
      selectedSchool.value = null
      if (!handleAuthError(error)) detailError.value = messageOf(error)
    } finally {
      detailLoading.value = false
    }
  }

  async function loadJobs(page = 1): Promise<void> {
    if (!token.value) return
    jobsLoading.value = true
    jobsError.value = ''
    try {
      const response = await adminApi.jobs(
        {
          status: jobFilters.status || undefined,
          review_status: jobFilters.review_status || undefined,
          page,
          page_size: PAGE_SIZE,
        },
        token.value,
      )
      jobs.value = response.items
      jobsTotal.value = response.total
      jobsPage.value = response.page
      jobsPages.value = response.pages
      if (jobs.value.some((job) => job.status === 'PENDING' || job.status === 'RUNNING')) startPolling()
      else stopPolling()
    } catch (error) {
      if (!handleAuthError(error)) jobsError.value = messageOf(error)
      jobs.value = []
    } finally {
      jobsLoading.value = false
    }
  }

  async function loadJob(id: number): Promise<void> {
    if (!token.value) return
    jobDetailId.value = id
    jobDetailLoading.value = true
    jobDetailError.value = ''
    try {
      selectedJob.value = await adminApi.job(id, token.value)
    } catch (error) {
      selectedJob.value = null
      if (!handleAuthError(error)) jobDetailError.value = messageOf(error)
    } finally {
      jobDetailLoading.value = false
    }
  }

  async function createJob(scope: Record<string, string | number | boolean | null>): Promise<boolean> {
    if (!token.value) return false
    actionPending.value = true
    actionError.value = ''
    notice.value = ''
    try {
      const result = await adminApi.createJob(scope, idempotencyKey(), token.value)
      notice.value = result.warning ?? (result.replayed ? '已复用相同幂等键的任务' : '质检任务已创建')
      await Promise.all([loadJobs(1), loadStats()])
      await loadJob(result.job.id)
      if (result.job.status === 'PENDING' || result.job.status === 'RUNNING') startPolling()
      return true
    } catch (error) {
      if (!handleAuthError(error)) actionError.value = messageOf(error)
      return false
    } finally {
      actionPending.value = false
    }
  }

  async function reviewJob(id: number, decision: 'APPROVED' | 'REJECTED', note: string): Promise<boolean> {
    if (!token.value || !selectedJob.value) return false
    actionPending.value = true
    actionError.value = ''
    notice.value = ''
    try {
      const updated = await adminApi.reviewJob(
        id,
        { decision, note, expected_version: selectedJob.value.job.version },
        token.value,
      )
      const index = jobs.value.findIndex((job) => job.id === id)
      if (index >= 0) jobs.value[index] = updated
      await loadJob(id)
      await loadStats()
      notice.value = decision === 'APPROVED' ? '审核通过，操作已写入审计日志' : '已驳回，操作已写入审计日志'
      return true
    } catch (error) {
      if (!handleAuthError(error)) actionError.value = messageOf(error)
      return false
    } finally {
      actionPending.value = false
    }
  }

  async function loadAudit(page = 1): Promise<void> {
    if (!token.value || !isAdmin.value) return
    auditLoading.value = true
    auditError.value = ''
    try {
      const response = await adminApi.auditLogs({ page, page_size: PAGE_SIZE }, token.value)
      auditLogs.value = response.items
      auditTotal.value = response.total
      auditPage.value = response.page
      auditPages.value = response.pages
    } catch (error) {
      if (!handleAuthError(error)) auditError.value = messageOf(error)
      auditLogs.value = []
    } finally {
      auditLoading.value = false
    }
  }

  async function refreshAll(): Promise<void> {
    if (!token.value) return
    await Promise.all([loadStats(), loadSystemStatus(), loadFilterOptions(), loadSchools(1), loadJobs(1)])
    if (isAdmin.value) await loadAudit(1)
  }

  function startPolling(): void {
    if (pollTimer !== null) return
    pollTimer = window.setInterval(() => {
      if (!token.value) {
        stopPolling()
        return
      }
      void loadJobs(jobsPage.value)
      if (selectedJob.value && ['PENDING', 'RUNNING'].includes(selectedJob.value.job.status)) {
        void loadJob(selectedJob.value.job.id)
      }
    }, 2500)
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
  }

  return {
    token,
    user,
    stats,
    systemStatus,
    filterOptions,
    filters,
    jobFilters,
    schools,
    schoolTotal,
    schoolPage,
    schoolPages,
    schoolsLoading,
    schoolsError,
    selectedSchool,
    schoolDetailId,
    detailLoading,
    detailError,
    jobs,
    jobsTotal,
    jobsPage,
    jobsPages,
    jobsLoading,
    jobsError,
    selectedJob,
    jobDetailId,
    jobDetailLoading,
    jobDetailError,
    auditLogs,
    auditTotal,
    auditPage,
    auditPages,
    auditLoading,
    auditError,
    actionPending,
    actionError,
    notice,
    isAuthenticated,
    role,
    canWrite,
    isAdmin,
    login,
    logout,
    loadStats,
    loadSystemStatus,
    loadFilterOptions,
    loadSchools,
    loadSchool,
    loadJobs,
    loadJob,
    createJob,
    reviewJob,
    loadAudit,
    refreshAll,
    startPolling,
    stopPolling,
  }
})
