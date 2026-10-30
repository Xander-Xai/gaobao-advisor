<template>
  <section class="space-y-4" aria-label="数据质检任务">
    <div
      v-if="admin.notice"
      role="status"
      data-testid="quality-notice"
      class="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"
    >{{ admin.notice }}</div>
    <div
      v-if="admin.actionError"
      role="alert"
      data-testid="quality-action-error"
      class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700"
    >{{ admin.actionError }}</div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,340px)_1fr]">
      <form class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" @submit.prevent="submitJob">
        <h2 class="text-sm font-semibold text-slate-800">发起数据质检</h2>
        <p class="mt-1 text-xs text-slate-400">Worker 会扫描所选范围内的院校、分数与招生计划，并生成可审核的问题清单。</p>

        <div class="mt-4 space-y-3">
          <div>
            <label for="job-province" class="block text-xs font-medium text-slate-500 mb-1">省份（可选）</label>
            <select id="job-province" v-model="scope.province" data-testid="job-province" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="">全部省份</option>
              <option v-for="item in admin.filterOptions.provinces" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label for="job-level" class="block text-xs font-medium text-slate-500 mb-1">层次（可选）</label>
            <select id="job-level" v-model="scope.level" data-testid="job-level" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="">全部层次</option>
              <option v-for="item in admin.filterOptions.levels" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label for="job-school-id" class="block text-xs font-medium text-slate-500 mb-1">院校 ID（可选）</label>
            <input
              id="job-school-id"
              v-model.number="scope.schoolId"
              data-testid="job-school-id"
              type="number"
              min="1"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="例如 1"
            />
          </div>
        </div>

        <button
          type="button"
          data-testid="create-job"
          :disabled="!admin.canWrite || admin.actionPending"
          @click="submitJob"
          class="mt-4 w-full rounded-lg bg-red-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-40"
        >{{ admin.actionPending ? '提交中…' : '创建质检任务' }}</button>
        <p v-if="!admin.canWrite" class="mt-2 text-xs text-amber-700">当前角色为 viewer，只能查看，不能创建任务。</p>
        <p class="mt-2 text-[11px] leading-relaxed text-slate-400">
          队列状态：{{ admin.systemStatus?.queue_state ?? 'UNKNOWN' }} · 模式：{{ admin.systemStatus?.task_mode ?? '—' }}
        </p>
      </form>

      <div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
          <h2 class="text-sm font-semibold text-slate-700">质检任务 <span class="font-normal text-slate-400">共 {{ admin.jobsTotal }} 条</span></h2>
          <div class="flex items-center gap-2 text-xs">
            <select v-model="admin.jobFilters.status" class="rounded-md border border-slate-300 bg-white px-2 py-1" @change="admin.loadJobs(1)">
              <option value="">全部状态</option>
              <option value="PENDING">PENDING</option>
              <option value="RUNNING">RUNNING</option>
              <option value="SUCCEEDED">SUCCEEDED</option>
              <option value="FAILED">FAILED</option>
            </select>
            <select v-model="admin.jobFilters.review_status" class="rounded-md border border-slate-300 bg-white px-2 py-1" @change="admin.loadJobs(1)">
              <option value="">全部审核</option>
              <option value="PENDING_REVIEW">待审核</option>
              <option value="APPROVED">已通过</option>
              <option value="REJECTED">已驳回</option>
            </select>
            <button class="rounded-md border border-slate-300 px-2 py-1 text-slate-600" @click="admin.loadJobs(admin.jobsPage)">刷新</button>
          </div>
        </div>

        <div v-if="admin.jobsLoading" class="space-y-2 p-4" data-testid="jobs-loading" aria-busy="true">
          <div v-for="n in 3" :key="n" class="h-10 animate-pulse rounded-lg bg-slate-100"></div>
        </div>
        <div v-else-if="admin.jobsError" role="alert" class="p-4 text-sm text-red-700" data-testid="jobs-error">
          加载任务失败：{{ admin.jobsError }}
          <button class="ml-2 underline" @click="admin.loadJobs(admin.jobsPage)">重试</button>
        </div>
        <div v-else-if="!admin.jobs.length" class="p-10 text-center" data-testid="jobs-empty">
          <p class="text-sm font-medium text-slate-600">还没有质检任务</p>
          <p class="mt-1 text-xs text-slate-400">在左侧选择范围并创建第一个任务</p>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200 text-sm">
            <caption class="sr-only">数据质检任务列表</caption>
            <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" class="px-4 py-2 font-medium">#</th>
                <th scope="col" class="px-3 py-2 font-medium">状态</th>
                <th scope="col" class="px-3 py-2 font-medium">审核</th>
                <th scope="col" class="px-3 py-2 text-right font-medium">问题</th>
                <th scope="col" class="px-3 py-2 font-medium">执行模式</th>
                <th scope="col" class="px-3 py-2 font-medium">创建人</th>
                <th scope="col" class="px-3 py-2 font-medium">时间</th>
                <th scope="col" class="px-4 py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="job in admin.jobs" :key="job.id" class="hover:bg-slate-50/80">
                <td class="px-4 py-2.5 font-mono text-slate-600">{{ job.id }}</td>
                <td class="px-3 py-2.5"><span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium" :class="statusClass(job.status)">{{ job.status }}</span></td>
                <td class="px-3 py-2.5"><span class="inline-flex rounded-full px-2 py-0.5 text-xs" :class="reviewClass(job.review_status)">{{ reviewLabel(job.review_status) }}</span></td>
                <td class="px-3 py-2.5 text-right font-mono text-slate-700">{{ job.issue_count }}</td>
                <td class="px-3 py-2.5 font-mono text-xs text-slate-500">{{ job.execution_mode }}</td>
                <td class="px-3 py-2.5 text-slate-600">{{ job.requested_by }}</td>
                <td class="px-3 py-2.5 text-xs text-slate-400">{{ formatTime(job.created_at) }}</td>
                <td class="px-4 py-2.5 text-right">
                  <button class="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-white" :data-testid="`job-detail-${job.id}`" @click="admin.loadJob(job.id)">详情</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex items-center justify-between border-t border-slate-200 px-4 py-3">
          <button class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40" :disabled="admin.jobsPage <= 1" @click="admin.loadJobs(admin.jobsPage - 1)">上一页</button>
          <span class="text-xs text-slate-400">第 {{ admin.jobsPage }} / {{ Math.max(1, admin.jobsPages) }} 页</span>
          <button class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40" :disabled="admin.jobsPage >= admin.jobsPages" @click="admin.loadJobs(admin.jobsPage + 1)">下一页</button>
        </div>

        <div v-if="admin.selectedJob" class="border-t border-slate-200 bg-slate-50/60 p-4" data-testid="job-detail">
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 class="text-sm font-semibold text-slate-800">任务 #{{ admin.selectedJob.job.id }} · {{ admin.selectedJob.job.status }}</h3>
              <p class="text-xs text-slate-500">范围：{{ formatFilters(admin.selectedJob.job.filters) }}</p>
              <p v-if="admin.selectedJob.job.error_message" class="mt-1 text-xs text-red-700">{{ admin.selectedJob.job.error_code }}：{{ admin.selectedJob.job.error_message }}</p>
            </div>
            <button class="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-600" @click="admin.selectedJob = null">关闭</button>
          </div>

          <div v-if="admin.jobDetailLoading" class="mt-3 text-sm text-slate-500" aria-busy="true">加载任务详情…</div>
          <div v-else-if="admin.jobDetailError" class="mt-3 text-sm text-red-700">
            {{ admin.jobDetailError }}
            <button v-if="admin.jobDetailId" class="ml-2 underline" @click="admin.loadJob(admin.jobDetailId)">重试</button>
          </div>
          <template v-else>
            <div class="mt-3 max-h-64 overflow-auto rounded-lg border border-slate-200 bg-white">
              <table class="min-w-full text-xs">
                <thead class="bg-slate-50 text-left text-slate-500">
                  <tr>
                    <th scope="col" class="px-2 py-1.5">级别</th>
                    <th scope="col" class="px-2 py-1.5">规则</th>
                    <th scope="col" class="px-2 py-1.5">实体</th>
                    <th scope="col" class="px-2 py-1.5">问题</th>
                    <th scope="col" class="px-2 py-1.5">建议</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="issue in admin.selectedJob.issues" :key="issue.id">
                    <td class="px-2 py-1.5"><span class="rounded px-1.5 py-0.5 font-medium" :class="severityClass(issue.severity)">{{ issue.severity }}</span></td>
                    <td class="px-2 py-1.5 font-mono text-slate-600">{{ issue.rule_code }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ issue.entity_type }}#{{ issue.entity_id }}</td>
                    <td class="px-2 py-1.5 text-slate-700">{{ issue.message }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ issue.suggestion ?? '—' }}</td>
                  </tr>
                  <tr v-if="!admin.selectedJob.issues.length">
                    <td colspan="5" class="px-2 py-4 text-center text-slate-400">本次质检未发现问题</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="admin.isAdmin && admin.selectedJob.job.status === 'SUCCEEDED' && admin.selectedJob.job.review_status === 'PENDING_REVIEW'" class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <label for="review-note" class="block text-xs font-medium text-amber-900 mb-1">审核备注</label>
              <textarea id="review-note" v-model="reviewNote" maxlength="500" rows="2" class="w-full rounded-md border border-amber-300 bg-white px-2 py-1.5 text-xs" placeholder="记录审核依据（写入审计日志）"></textarea>
              <div class="mt-2 flex gap-2">
                <button class="rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40" :disabled="admin.actionPending" data-testid="review-approve" @click="review('APPROVED')">审核通过</button>
                <button class="rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40" :disabled="admin.actionPending" data-testid="review-reject" @click="review('REJECTED')">驳回</button>
              </div>
            </div>
            <p v-else-if="admin.selectedJob.job.review_status !== 'PENDING_REVIEW'" class="mt-3 text-xs text-slate-500">
              审核结果：{{ reviewLabel(admin.selectedJob.job.review_status) }} · {{ admin.selectedJob.job.reviewed_by ?? '—' }} · {{ admin.selectedJob.job.review_note ?? '无备注' }}
            </p>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'
import type { JobStatus, ReviewStatus, Severity } from '../../types/admin'

const admin = useAdminStore()
const scope = reactive<{ province: string; level: string; schoolId: number | null }>({
  province: '',
  level: '',
  schoolId: null,
})
const reviewNote = ref('')

function submitJob(): void {
  const filters: Record<string, string | number> = {}
  if (scope.province) filters.province = scope.province
  if (scope.level) filters.level = scope.level
  if (scope.schoolId) filters.school_id = scope.schoolId
  void admin.createJob(filters)
}

function review(decision: 'APPROVED' | 'REJECTED'): void {
  if (!admin.selectedJob) return
  void admin.reviewJob(admin.selectedJob.job.id, decision, reviewNote.value).then((ok) => {
    if (ok) reviewNote.value = ''
  })
}

function statusClass(status: JobStatus): string {
  return {
    PENDING: 'bg-amber-100 text-amber-800',
    RUNNING: 'bg-sky-100 text-sky-800',
    SUCCEEDED: 'bg-emerald-100 text-emerald-800',
    FAILED: 'bg-red-100 text-red-800',
  }[status]
}

function reviewClass(status: ReviewStatus): string {
  return {
    PENDING_REVIEW: 'bg-slate-100 text-slate-600',
    APPROVED: 'bg-emerald-100 text-emerald-700',
    REJECTED: 'bg-red-100 text-red-700',
  }[status]
}

function reviewLabel(status: ReviewStatus): string {
  return { PENDING_REVIEW: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }[status]
}

function severityClass(severity: Severity): string {
  return {
    ERROR: 'bg-red-100 text-red-700',
    WARNING: 'bg-amber-100 text-amber-800',
    INFO: 'bg-slate-100 text-slate-600',
  }[severity]
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}

function formatFilters(filters: Record<string, unknown>): string {
  const entries = Object.entries(filters).filter(([, value]) => value !== null && value !== '')
  if (!entries.length) return '全部合成数据'
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(' · ')
}
</script>
