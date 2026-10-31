<template>
  <section
    v-if="store.detailLoading || store.detailError || store.selectedSchool"
    class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200"
    aria-label="院校数据详情"
    data-testid="data-school-detail"
  >
    <div v-if="store.detailLoading" class="space-y-3" aria-busy="true">
      <div class="h-7 w-1/3 animate-pulse rounded bg-slate-100"></div>
      <div class="h-40 animate-pulse rounded-xl bg-slate-100"></div>
    </div>

    <div v-else-if="store.detailError" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p>院校详情加载失败：{{ store.detailError }}</p>
      <button class="mt-3 rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium" @click="retry">重试</button>
    </div>

    <template v-else-if="store.selectedSchool">
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-slate-900">{{ store.selectedSchool.name }}</h2>
          <p class="mt-1 text-xs text-slate-500">
            {{ store.selectedSchool.province }} · {{ store.selectedSchool.city }} ·
            {{ store.selectedSchool.level }} · {{ store.selectedSchool.school_type }}
          </p>
        </div>
        <button class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50" @click="store.closeSchool()">
          关闭
        </button>
      </header>

      <p v-if="store.selectedSchool.description" class="mt-3 text-xs leading-relaxed text-slate-500">
        {{ store.selectedSchool.description }}
      </p>

      <div class="mt-4 flex flex-wrap gap-2 text-[11px]">
        <span class="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">录取记录 {{ store.selectedSchool.score_count }}</span>
        <span class="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">招生计划 {{ store.selectedSchool.plan_count }}</span>
        <span class="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
          可用年份 {{ store.selectedSchool.data_availability.available_years.join(' / ') || '—' }}
        </span>
        <span v-if="!store.selectedSchool.data_availability.has_scores" class="rounded-full bg-amber-100 px-2.5 py-1 text-amber-800">
          暂无录取分数
        </span>
        <span v-if="!store.selectedSchool.data_availability.has_plans" class="rounded-full bg-amber-100 px-2.5 py-1 text-amber-800">
          暂无招生计划
        </span>
      </div>

      <div class="mt-5 rounded-xl border border-slate-200 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 class="text-sm font-semibold text-slate-800">录取分数趋势</h3>
            <p class="mt-1 text-[11px] text-slate-400">按科类分别绘制，不混合不同省份或考试模式的口径。</p>
          </div>
          <div class="flex flex-wrap items-end gap-2">
            <div>
              <label for="trend-major" class="mb-1 block text-[11px] text-slate-400">专业</label>
              <select
                id="trend-major"
                v-model="store.trendMajor"
                class="max-w-52 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs"
                @change="store.loadTrend()"
              >
                <option value="">全部专业（取最低分）</option>
                <option v-for="major in majors" :key="major" :value="major">{{ major }}</option>
              </select>
            </div>
          </div>
        </div>

        <div v-if="subjects.length > 1" class="mt-3 flex flex-wrap gap-1.5" role="tablist" aria-label="科类">
          <button
            v-for="subject in subjects"
            :key="subject"
            type="button"
            role="tab"
            :aria-selected="store.selectedSubject === subject"
            :class="[
              'rounded-full px-3 py-1 text-xs transition-colors',
              store.selectedSubject === subject ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
            ]"
            @click="store.selectedSubject = subject"
          >
            {{ subject }}
          </button>
        </div>

        <div v-if="store.trendError" role="alert" class="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          趋势加载失败：{{ store.trendError }}
          <button class="ml-2 underline" @click="store.loadTrend()">重试</button>
        </div>
        <div v-else-if="store.trendLoading" class="mt-4 h-56 animate-pulse rounded-xl bg-slate-100" aria-busy="true"></div>
        <template v-else>
          <ScoreTrendChart class="mt-4" :series="store.visibleSeries" />
          <p v-if="store.trend" class="mt-3 text-[11px] leading-relaxed text-slate-400">
            {{ store.trend.notice }}
            <span v-if="store.trend.missing_years.length"> 缺失年份：{{ store.trend.missing_years.join('、') }}。</span>
          </p>
        </template>
      </div>

      <div class="mt-4 grid gap-4 xl:grid-cols-2">
        <div class="rounded-xl border border-slate-200">
          <div class="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">录取分数</h3>
            <span class="text-[11px] text-slate-400">最近 {{ store.selectedSchool.scores.length }} 条</span>
          </div>
          <div class="max-h-64 overflow-auto">
            <table class="min-w-full text-xs">
              <caption class="sr-only">院校录取分数明细</caption>
              <thead class="sticky top-0 bg-slate-50 text-left text-slate-500">
                <tr>
                  <th scope="col" class="px-2 py-1.5">专业</th>
                  <th scope="col" class="px-2 py-1.5">年份</th>
                  <th scope="col" class="px-2 py-1.5">科类</th>
                  <th scope="col" class="px-2 py-1.5 text-right">最低</th>
                  <th scope="col" class="px-2 py-1.5 text-right">平均</th>
                  <th scope="col" class="px-2 py-1.5 text-right">位次</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="score in store.selectedSchool.scores" :key="score.id">
                  <td class="px-2 py-1.5 text-slate-700">{{ score.major_name ?? '院校线' }}</td>
                  <td class="px-2 py-1.5 text-slate-500">{{ score.year }}</td>
                  <td class="px-2 py-1.5 text-slate-500">{{ score.subject_type }}</td>
                  <td class="px-2 py-1.5 text-right font-mono">{{ score.min_score ?? '—' }}</td>
                  <td class="px-2 py-1.5 text-right font-mono">{{ score.avg_score ?? '—' }}</td>
                  <td class="px-2 py-1.5 text-right font-mono">{{ score.min_rank ?? '—' }}</td>
                </tr>
                <tr v-if="!store.selectedSchool.scores.length">
                  <td colspan="6" class="px-2 py-6 text-center text-slate-400">暂无分数记录</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="rounded-xl border border-slate-200">
          <div class="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-slate-500">招生计划</h3>
            <span class="text-[11px] text-slate-400">最近 {{ store.selectedSchool.plans.length }} 条</span>
          </div>
          <div class="max-h-64 overflow-auto">
            <table class="min-w-full text-xs">
              <caption class="sr-only">院校招生计划明细</caption>
              <thead class="sticky top-0 bg-slate-50 text-left text-slate-500">
                <tr>
                  <th scope="col" class="px-2 py-1.5">专业</th>
                  <th scope="col" class="px-2 py-1.5">年份</th>
                  <th scope="col" class="px-2 py-1.5">省份</th>
                  <th scope="col" class="px-2 py-1.5 text-right">计划</th>
                  <th scope="col" class="px-2 py-1.5">选科</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="plan in store.selectedSchool.plans" :key="plan.id">
                  <td class="px-2 py-1.5 text-slate-700">{{ plan.major_name ?? '—' }}</td>
                  <td class="px-2 py-1.5 text-slate-500">{{ plan.year }}</td>
                  <td class="px-2 py-1.5 text-slate-500">{{ plan.province }}</td>
                  <td class="px-2 py-1.5 text-right font-mono">{{ plan.plan_count ?? '—' }}</td>
                  <td class="px-2 py-1.5 text-slate-500">{{ plan.subject_requirement ?? '—' }}</td>
                </tr>
                <tr v-if="!store.selectedSchool.plans.length">
                  <td colspan="5" class="px-2 py-6 text-center text-slate-400">暂无招生计划</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import ScoreTrendChart from './ScoreTrendChart.vue'
import { useDataCatalogStore } from '../../stores/dataCatalog'

const store = useDataCatalogStore()
const majors = computed(() => store.filterOptions?.majors || [])
const subjects = computed(() => (store.trend?.series || []).map(series => series.subject_type))

function retry() {
  if (store.selectedSchoolId) void store.selectSchool(store.selectedSchoolId)
}
</script>
