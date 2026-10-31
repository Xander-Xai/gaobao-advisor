<template>
  <section aria-label="院校浏览" data-testid="school-browser">
    <form class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200" @submit.prevent="search">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <div class="xl:col-span-2">
          <label for="data-school-q" class="mb-1 block text-xs font-medium text-slate-500">院校 / 城市</label>
          <input
            id="data-school-q"
            v-model="store.filters.q"
            data-testid="data-school-q"
            class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            placeholder="例如：北辰 / 示例市·晨"
          />
        </div>
        <div>
          <label for="data-province" class="mb-1 block text-xs font-medium text-slate-500">省份</label>
          <select id="data-province" v-model="store.filters.province" class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="">全部</option>
            <option v-for="item in provinces" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
        <div>
          <label for="data-level" class="mb-1 block text-xs font-medium text-slate-500">层次</label>
          <select id="data-level" v-model="store.filters.level" class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">
            <option value="">全部</option>
            <option v-for="item in levels" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
        <div class="flex items-end gap-2">
          <div class="flex-1">
            <label for="data-type" class="mb-1 block text-xs font-medium text-slate-500">类型</label>
            <select id="data-type" v-model="store.filters.schoolType" class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm">
              <option value="">全部</option>
              <option v-for="item in schoolTypes" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <button type="submit" class="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
            查询
          </button>
        </div>
      </div>
      <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <span>数据来源：{{ sourceLabel }} · 展示记录均来自当前数据库查询</span>
        <button v-if="store.hasActiveFilters" type="button" class="text-slate-500 underline hover:text-slate-800" @click="store.resetFilters()">
          清空筛选
        </button>
      </div>
    </form>

    <div class="mt-4 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 class="text-sm font-semibold text-slate-800">
          院校列表
          <span class="font-normal text-slate-400">共 {{ store.total }} 所</span>
        </h2>
        <span class="text-xs text-slate-400">已加载 {{ store.schools.length }} 所</span>
      </div>

      <div v-if="store.schoolsError" role="alert" class="m-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <span>院校列表加载失败：{{ store.schoolsError }}</span>
        <button class="rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium" @click="store.loadSchools()">重试</button>
      </div>

      <div v-else-if="store.schoolsLoading && !store.schools.length" class="space-y-2 p-4" aria-busy="true">
        <div v-for="n in 5" :key="n" class="h-12 animate-pulse rounded-xl bg-slate-100"></div>
      </div>

      <div v-else-if="!store.schools.length" class="p-10 text-center" data-testid="data-schools-empty">
        <p class="text-sm font-medium text-slate-600">没有匹配的院校</p>
        <p class="mt-1 text-xs text-slate-400">调整关键词、省份或层次后重试</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
          <caption class="sr-only">可浏览的院校及数据覆盖情况</caption>
          <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" class="px-4 py-2.5 font-medium">院校</th>
              <th scope="col" class="px-3 py-2.5 font-medium">省份</th>
              <th scope="col" class="px-3 py-2.5 font-medium">层次 / 类型</th>
              <th scope="col" class="px-3 py-2.5 text-right font-medium">录取记录</th>
              <th scope="col" class="px-3 py-2.5 text-right font-medium">最新最低分</th>
              <th scope="col" class="px-4 py-2.5 text-right font-medium">详情</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr
              v-for="school in store.schools"
              :key="school.id"
              :class="['transition-colors', store.selectedSchool?.id === school.id ? 'bg-blue-50/70' : 'hover:bg-slate-50']"
            >
              <td class="px-4 py-3">
                <p class="font-medium text-slate-800">{{ school.name }}</p>
                <p class="text-[11px] text-slate-400">{{ school.city }} · 排名 {{ school.ranking ?? '—' }}</p>
              </td>
              <td class="px-3 py-3 text-slate-600">{{ school.province }}</td>
              <td class="px-3 py-3">
                <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{{ school.level }}</span>
                <span class="ml-1 text-xs text-slate-400">{{ school.school_type }}</span>
              </td>
              <td class="px-3 py-3 text-right font-mono text-slate-700">{{ school.score_count }}</td>
              <td class="px-3 py-3 text-right font-mono text-slate-700">
                {{ school.latest_min_score ?? '—' }}
                <span class="ml-1 text-[11px] text-slate-400">{{ school.latest_year ?? '' }}</span>
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  type="button"
                  class="rounded-lg border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-white"
                  :data-testid="`data-school-${school.id}`"
                  :aria-label="`查看 ${school.name} 的分数与趋势`"
                  @click="store.selectSchool(school.id)"
                >
                  查看趋势
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="store.schools.length" class="flex items-center justify-between border-t border-slate-200 px-4 py-3">
        <span class="text-xs text-slate-400">游标分页 · 每页 6 所</span>
        <button
          v-if="store.hasMore"
          type="button"
          class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-40"
          :disabled="store.schoolsLoading"
          @click="store.loadSchools({ append: true })"
        >
          {{ store.schoolsLoading ? '加载中…' : '加载更多' }}
        </button>
        <span v-else class="text-xs text-slate-400">已全部加载</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useDataCatalogStore } from '../../stores/dataCatalog'

const store = useDataCatalogStore()
const provinces = computed(() => store.filterOptions?.provinces || [])
const levels = computed(() => store.filterOptions?.levels || [])
const schoolTypes = computed(() => store.filterOptions?.school_types || [])
const sourceLabel = computed(() => {
  const profile = store.overview?.data_profile
  return {
    SYNTHETIC_DEMO: 'SYNTHETIC_DEMO 合成演示数据',
    CUSTOM: '部署者导入的自有数据',
    MIXED: '合成与自有数据混合',
    EMPTY: '空数据库',
    UNKNOWN: '来源未知',
  }[profile] || '来源未知'
})

function search() {
  void store.applyFilters()
}
</script>
