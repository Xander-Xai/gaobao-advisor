<template>
  <section aria-label="数据概览" data-testid="data-overview">
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true">
      <div v-for="n in 4" :key="n" class="h-28 animate-pulse rounded-2xl bg-white/70 ring-1 ring-slate-200"></div>
    </div>

    <div v-else-if="error" role="alert" class="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
      <p>数据概览加载失败：{{ error }}</p>
      <button class="mt-3 rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium" @click="$emit('retry')">
        重试
      </button>
    </div>

    <div v-else-if="!overview" class="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
      暂无数据概览。请先初始化演示数据。
    </div>

    <template v-else>
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <p class="text-xs font-medium uppercase tracking-wide text-slate-400">院校</p>
          <p class="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{{ formatNumber(overview.counts.schools) }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ overview.provinces.length }} 个省份 · {{ overview.school_types.length }} 种类型</p>
        </article>
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <p class="text-xs font-medium uppercase tracking-wide text-slate-400">专业</p>
          <p class="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{{ formatNumber(overview.counts.majors) }}</p>
          <p class="mt-1 text-xs text-slate-500">招生计划 {{ formatNumber(overview.counts.enrollment_plans) }} 条</p>
        </article>
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <p class="text-xs font-medium uppercase tracking-wide text-slate-400">录取记录</p>
          <p class="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{{ formatNumber(overview.counts.admission_scores) }}</p>
          <p class="mt-1 text-xs text-slate-500">位次映射 {{ formatNumber(overview.counts.score_rank_rows) }} 条</p>
        </article>
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <p class="text-xs font-medium uppercase tracking-wide text-slate-400">数据年份</p>
          <p class="mt-2 text-3xl font-semibold tabular-nums text-slate-900">{{ yearRange }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ overview.scores_by_year.length }} 个招生年份</p>
        </article>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <article class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-sm font-semibold text-slate-800">逐年记录覆盖</h2>
            <span class="text-xs text-slate-400">按录取记录数统计</span>
          </div>
          <div v-if="overview.scores_by_year.length" class="mt-4 space-y-3" data-testid="coverage-bars">
            <div v-for="item in overview.scores_by_year" :key="item.year" class="flex items-center gap-3">
              <span class="w-12 shrink-0 text-xs tabular-nums text-slate-500">{{ item.year }}</span>
              <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400" :style="{ width: barWidth(item.count) }"></div>
              </div>
              <span class="w-14 shrink-0 text-right text-xs tabular-nums text-slate-500">{{ formatNumber(item.count) }}</span>
            </div>
          </div>
          <p v-else class="mt-4 text-sm text-slate-400">暂无录取记录。</p>
        </article>

        <article class="rounded-2xl bg-slate-900 p-5 text-slate-100 shadow-sm">
          <div class="flex items-center justify-between gap-2">
            <h2 class="text-sm font-semibold">数据画像</h2>
            <span :class="profileClass">{{ profileLabel }}</span>
          </div>
          <dl class="mt-4 space-y-2.5 text-xs">
            <div class="flex items-center justify-between gap-3">
              <dt class="text-slate-400">覆盖年份</dt>
              <dd class="tabular-nums">{{ yearRange }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-slate-400">数据集版本</dt>
              <dd>{{ overview.snapshot?.dataset_version ?? '未登记' }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-slate-400">生成时间</dt>
              <dd class="text-right">{{ generatedAt }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3">
              <dt class="text-slate-400">有分数院校</dt>
              <dd class="tabular-nums">{{ formatNumber(overview.schools_with_scores) }}</dd>
            </div>
          </dl>
          <p class="mt-4 border-t border-white/10 pt-3 text-[11px] leading-relaxed text-slate-400">
            {{ overview.notice }}
          </p>
        </article>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  overview: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
defineEmits(['retry'])

const maxYearCount = computed(() => Math.max(1, ...(props.overview?.scores_by_year || []).map(item => item.count)))
const yearRange = computed(() => {
  const from = props.overview?.year_from
  const to = props.overview?.year_to
  if (!from || !to) return '—'
  return from === to ? String(from) : `${from}–${to}`
})
const profileLabel = computed(() => {
  const profile = props.overview?.data_profile
  return {
    SYNTHETIC_DEMO: '合成演示',
    CUSTOM: '自有数据',
    MIXED: '混合数据',
    EMPTY: '空数据',
    UNKNOWN: '来源未知',
  }[profile] || profile || '未知'
})
const profileClass = computed(() => {
  const profile = props.overview?.data_profile
  const base = 'rounded-full px-2.5 py-0.5 text-[11px] font-medium'
  if (profile === 'SYNTHETIC_DEMO') return `${base} bg-amber-400/20 text-amber-200`
  if (profile === 'CUSTOM') return `${base} bg-emerald-400/20 text-emerald-200`
  if (profile === 'MIXED') return `${base} bg-sky-400/20 text-sky-200`
  return `${base} bg-white/10 text-slate-300`
})
const generatedAt = computed(() => {
  const value = props.overview?.snapshot?.generated_at
  if (!value) return '未登记'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
})

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function barWidth(count) {
  return `${Math.max(3, Math.round((Number(count) / maxYearCount.value) * 100))}%`
}
</script>
