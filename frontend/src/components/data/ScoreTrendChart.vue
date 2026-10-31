<template>
  <div data-testid="score-trend-chart">
    <div v-if="!series.length" class="flex h-56 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
      暂无可绘制的趋势数据
    </div>

    <template v-else>
      <div v-if="availableYears.length < 2" class="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
        仅有 {{ availableYears.length }} 个年份有数据，无法判断趋势。
      </div>
      <svg
        class="h-64 w-full"
        viewBox="0 0 720 260"
        role="img"
        :aria-label="chartLabel"
      >
        <g class="text-[11px] fill-slate-400">
          <line v-for="tick in yTicks" :key="`y-${tick}`" x1="56" :y1="yScale(tick)" x2="704" :y2="yScale(tick)" stroke="#e2e8f0" stroke-width="1" />
          <text v-for="tick in yTicks" :key="`yl-${tick}`" x="48" :y="yScale(tick) + 4" text-anchor="end">{{ tick }}</text>
          <text v-for="year in years" :key="`x-${year}`" :x="xScale(year)" y="236" text-anchor="middle">{{ year }}</text>
        </g>

        <g v-for="(item, index) in series" :key="item.subject_type">
          <polyline
            :points="linePoints(item)"
            fill="none"
            :stroke="color(index)"
            stroke-width="2.5"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <circle
            v-for="point in plottedPoints(item)"
            :key="`${item.subject_type}-${point.year}`"
            :cx="xScale(point.year)"
            :cy="yScale(point.min_score)"
            r="4.5"
            :fill="color(index)"
            stroke="#fff"
            stroke-width="2"
          >
            <title>{{ item.subject_type }} · {{ point.year }} 年最低分 {{ point.min_score }}（{{ point.record_count }} 条记录）</title>
          </circle>
        </g>
      </svg>

      <div class="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span v-for="(item, index) in series" :key="`legend-${item.subject_type}`" class="inline-flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: color(index) }"></span>
          {{ item.subject_type }}
          <span class="text-slate-400">· {{ item.direction }}<template v-if="item.change !== null">（{{ item.change > 0 ? '+' : '' }}{{ item.change }} 分）</template></span>
        </span>
      </div>

      <details class="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <summary class="cursor-pointer select-none text-slate-500">查看数据表</summary>
        <div class="mt-3 overflow-x-auto">
          <div v-for="item in series" :key="`table-${item.subject_type}`" class="mb-3">
            <p class="mb-1 font-medium text-slate-700">{{ item.subject_type }}</p>
            <table class="min-w-full text-left">
              <thead class="text-slate-400">
                <tr>
                  <th scope="col" class="py-1 pr-4 font-medium">科类</th>
                  <th scope="col" class="py-1 pr-4 font-medium">年份</th>
                  <th scope="col" class="py-1 pr-4 text-right font-medium">最低分</th>
                  <th scope="col" class="py-1 pr-4 text-right font-medium">平均分</th>
                  <th scope="col" class="py-1 pr-4 text-right font-medium">最低位次</th>
                  <th scope="col" class="py-1 text-right font-medium">记录数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="point in item.points" :key="`${item.subject_type}-${point.year}-row`" class="border-t border-slate-200">
                  <td class="py-1 pr-4 text-slate-500">{{ item.subject_type }}</td>
                  <td class="py-1 pr-4 tabular-nums">{{ point.year }}</td>
                  <td class="py-1 pr-4 text-right tabular-nums">{{ point.min_score ?? '—' }}</td>
                  <td class="py-1 pr-4 text-right tabular-nums">{{ point.avg_score ?? '—' }}</td>
                  <td class="py-1 pr-4 text-right tabular-nums">{{ point.min_rank ?? '—' }}</td>
                  <td class="py-1 text-right tabular-nums">{{ point.record_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] },
})

const palette = ['#2563eb', '#f59e0b', '#10b981', '#8b5cf6']
const years = computed(() => {
  const values = new Set()
  for (const item of props.series) for (const point of item.points || []) values.add(point.year)
  return [...values].sort((a, b) => a - b)
})
const availableYears = computed(() => years.value.filter(year => plottedPointsForYear(year)))
const scoreValues = computed(() => {
  const values = []
  for (const item of props.series) {
    for (const point of item.points || []) {
      if (Number.isFinite(point.min_score)) values.push(point.min_score)
    }
  }
  return values
})
const yMin = computed(() => Math.max(0, Math.floor((Math.min(...scoreValues.value) - 10) / 10) * 10))
const yMax = computed(() => Math.min(750, Math.ceil((Math.max(...scoreValues.value) + 10) / 10) * 10))
const yTicks = computed(() => {
  const min = Number.isFinite(yMin.value) ? yMin.value : 300
  const max = Number.isFinite(yMax.value) ? yMax.value : 750
  const step = Math.max(10, Math.ceil((max - min) / 4 / 10) * 10)
  const ticks = []
  for (let value = min; value <= max; value += step) ticks.push(value)
  return ticks
})
const chartLabel = computed(() => {
  const labels = props.series.map(item => `${item.subject_type}：${item.points.map(point => `${point.year} 年 ${point.min_score ?? '无数据'} 分`).join('，')}`)
  return `录取分数趋势。${labels.join('；')}`
})

function plottedPointsForYear(year) {
  return props.series.some(item => (item.points || []).some(point => point.year === year && Number.isFinite(point.min_score)))
}

function plottedPoints(item) {
  return (item.points || []).filter(point => Number.isFinite(point.min_score))
}

function xScale(year) {
  if (years.value.length <= 1) return 380
  const min = years.value[0]
  const max = years.value[years.value.length - 1]
  return 56 + ((year - min) / (max - min)) * (704 - 56)
}

function yScale(value) {
  const min = Number.isFinite(yMin.value) ? yMin.value : 300
  const max = Number.isFinite(yMax.value) ? yMax.value : 750
  if (max === min) return 130
  return 24 + ((max - value) / (max - min)) * (212 - 24)
}

function linePoints(item) {
  return plottedPoints(item).map(point => `${xScale(point.year)},${yScale(point.min_score)}`).join(' ')
}

function color(index) {
  return palette[index % palette.length]
}
</script>
