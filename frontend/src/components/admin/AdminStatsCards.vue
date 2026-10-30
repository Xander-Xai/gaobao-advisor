<template>
  <section aria-label="运营统计" class="space-y-4">
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-6">
      <article
        v-for="card in cards"
        :key="card.label"
        class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{{ card.label }}</p>
        <p class="mt-2 text-2xl font-bold text-slate-900" data-testid="stat-value">{{ card.value }}</p>
        <p class="mt-1 text-xs text-slate-400">{{ card.hint }}</p>
      </article>
    </div>

    <div class="grid gap-3 lg:grid-cols-3">
      <article class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 class="text-sm font-semibold text-slate-700">任务状态分布</h2>
        <div class="mt-3 space-y-2">
          <div v-for="row in jobRows" :key="row.label" class="grid grid-cols-[72px_1fr_32px] items-center gap-2">
            <span class="text-xs text-slate-500">{{ row.label }}</span>
            <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div class="h-full rounded-full" :class="row.color" :style="{ width: row.width }"></div>
            </div>
            <span class="text-right text-xs font-medium text-slate-700">{{ row.value }}</span>
          </div>
        </div>
      </article>

      <article class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 class="text-sm font-semibold text-slate-700">问题严重度</h2>
        <div class="mt-3 space-y-2">
          <div v-for="row in severityRows" :key="row.label" class="grid grid-cols-[72px_1fr_32px] items-center gap-2">
            <span class="text-xs text-slate-500">{{ row.label }}</span>
            <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div class="h-full rounded-full" :class="row.color" :style="{ width: row.width }"></div>
            </div>
            <span class="text-right text-xs font-medium text-slate-700">{{ row.value }}</span>
          </div>
        </div>
      </article>

      <article class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 class="text-sm font-semibold text-slate-700">运行环境</h2>
        <dl class="mt-3 space-y-2 text-xs">
          <div class="flex items-center justify-between gap-2">
            <dt class="text-slate-500">数据库</dt>
            <dd class="font-mono text-slate-800">{{ systemStatus?.database_dialect ?? '—' }}</dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-slate-500">任务模式</dt>
            <dd class="font-mono text-slate-800">{{ systemStatus?.task_mode ?? '—' }}</dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-slate-500">队列</dt>
            <dd>
              <span
                class="inline-flex rounded-full px-2 py-0.5 font-medium"
                :class="queueClass"
                data-testid="queue-state"
              >{{ systemStatus?.queue_state ?? 'UNKNOWN' }}</span>
            </dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-slate-500">数据画像</dt>
            <dd class="font-mono text-slate-800">{{ stats?.data_profile ?? '—' }}</dd>
          </div>
        </dl>
        <p class="mt-3 text-[11px] leading-relaxed text-slate-400">{{ systemStatus?.worker_hint ?? '' }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Stats, SystemStatus } from '../../types/admin'

const props = defineProps<{
  stats: Stats | null
  systemStatus: SystemStatus | null
}>()

const cards = computed(() => [
  { label: '院校', value: props.stats?.schools ?? '—', hint: '合成招生数据' },
  { label: '专业', value: props.stats?.majors ?? '—', hint: '专业目录' },
  { label: '录取分数', value: props.stats?.admission_scores ?? '—', hint: '分数记录' },
  { label: '招生计划', value: props.stats?.enrollment_plans ?? '—', hint: '计划记录' },
  { label: '质检任务', value: props.stats?.jobs_total ?? '—', hint: '累计创建' },
  { label: '待审核', value: props.stats?.pending_review ?? '—', hint: 'SUCCEEDED 且未审核' },
])

const jobRows = computed(() => {
  const values = props.stats?.jobs_by_status ?? {}
  const max = Math.max(1, ...Object.values(values), 1)
  const rows = [
    { key: 'SUCCEEDED', label: '成功', color: 'bg-emerald-500' },
    { key: 'PENDING', label: '排队', color: 'bg-amber-400' },
    { key: 'RUNNING', label: '执行中', color: 'bg-sky-500' },
    { key: 'FAILED', label: '失败', color: 'bg-red-500' },
  ]
  return rows.map((row) => {
    const value = values[row.key] ?? 0
    return { ...row, value, width: `${Math.max(4, Math.round((value / max) * 100))}%` }
  })
})

const severityRows = computed(() => {
  const values = props.stats?.issues_by_severity ?? {}
  const max = Math.max(1, ...Object.values(values), 1)
  const rows = [
    { key: 'ERROR', label: '错误', color: 'bg-red-500' },
    { key: 'WARNING', label: '警告', color: 'bg-amber-400' },
    { key: 'INFO', label: '提示', color: 'bg-slate-400' },
  ]
  return rows.map((row) => {
    const value = values[row.key] ?? 0
    return { ...row, value, width: `${Math.max(4, Math.round((value / max) * 100))}%` }
  })
})

const queueClass = computed(() => {
  switch (props.systemStatus?.queue_state) {
    case 'READY':
      return 'bg-emerald-100 text-emerald-700'
    case 'UNAVAILABLE':
      return 'bg-amber-100 text-amber-800'
    default:
      return 'bg-slate-100 text-slate-600'
  }
})
</script>
