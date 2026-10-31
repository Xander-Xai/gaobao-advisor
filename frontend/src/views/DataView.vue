<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <RouterLink to="/" class="flex items-center gap-2.5">
          <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-sm font-semibold text-white">GB</span>
          <span>
            <span class="block text-sm font-semibold tracking-tight">gaobao-advisor</span>
            <span class="block text-[11px] text-slate-400">志愿决策辅助 · 数据浏览器</span>
          </span>
        </RouterLink>
        <nav class="flex items-center gap-1 text-sm" aria-label="主导航">
          <RouterLink to="/" class="rounded-lg px-3 py-1.5 text-slate-600 hover:bg-slate-100">智能问答</RouterLink>
          <RouterLink to="/data" class="rounded-lg bg-slate-900 px-3 py-1.5 font-medium text-white">数据浏览</RouterLink>
          <RouterLink to="/admin" class="rounded-lg px-3 py-1.5 text-slate-500 hover:bg-slate-100">运营后台</RouterLink>
        </nav>
      </div>
    </header>

    <main class="mx-auto max-w-7xl px-4 py-6">
      <section class="overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 px-6 py-8 text-white shadow-lg">
        <div class="flex flex-wrap items-start justify-between gap-6">
          <div class="max-w-2xl">
            <p class="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-[11px] font-medium text-blue-100">
              <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
              可核验数据 · 查询与程序计算
            </p>
            <h1 class="mt-4 text-2xl font-semibold tracking-tight sm:text-3xl">用数据理解院校与分数趋势</h1>
            <p class="mt-3 text-sm leading-relaxed text-slate-300">
              浏览院校覆盖、招生计划与分省分数记录。所有指标均来自当前数据库查询；
              默认演示库为程序生成的 SYNTHETIC_DEMO 合成数据，不对应任何真实院校或录取结果。
            </p>
          </div>
          <div class="grid grid-cols-2 gap-3 text-left text-xs">
            <div class="rounded-2xl bg-white/10 px-4 py-3">
              <p class="text-slate-400">数据标识</p>
              <p class="mt-1 font-medium">{{ profileLabel }}</p>
            </div>
            <div class="rounded-2xl bg-white/10 px-4 py-3">
              <p class="text-slate-400">查询方式</p>
              <p class="mt-1 font-medium">后端筛选 / 分页</p>
            </div>
            <div class="rounded-2xl bg-white/10 px-4 py-3">
              <p class="text-slate-400">趋势口径</p>
              <p class="mt-1 font-medium">同校 · 同省 · 同科类</p>
            </div>
            <div class="rounded-2xl bg-white/10 px-4 py-3">
              <p class="text-slate-400">辅助定位</p>
              <p class="mt-1 font-medium">不构成录取保证</p>
            </div>
          </div>
        </div>
      </section>

      <div class="mt-6">
        <DataOverview
          :overview="store.overview"
          :loading="store.overviewLoading"
          :error="store.overviewError"
          @retry="store.loadOverview()"
        />
      </div>

      <div class="mt-6">
        <SchoolBrowser />
      </div>

      <SchoolDetailPanel class="mt-4" />

      <footer class="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 py-5 text-xs text-slate-400">
        <p>
          数据说明：
          <a class="underline hover:text-slate-600" href="https://github.com/Xander-Xai/gaobao-advisor/blob/master/DATA_LICENSE.md" target="_blank" rel="noopener noreferrer">DATA_LICENSE.md</a>
          · 合成数据以 CC0-1.0 提供；历史录取数据不代表未来录取结果。
        </p>
        <RouterLink to="/" class="rounded-lg border border-slate-300 px-3 py-1.5 text-slate-600 hover:bg-white">
          返回智能问答
        </RouterLink>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import DataOverview from '../components/data/DataOverview.vue'
import SchoolBrowser from '../components/data/SchoolBrowser.vue'
import SchoolDetailPanel from '../components/data/SchoolDetailPanel.vue'
import { useDataCatalogStore } from '../stores/dataCatalog'

const store = useDataCatalogStore()
const profileLabel = computed(() => {
  const profile = store.overview?.data_profile
  return {
    SYNTHETIC_DEMO: 'SYNTHETIC_DEMO 合成演示',
    CUSTOM: '自有数据',
    MIXED: '混合数据',
    EMPTY: '空数据库',
    UNKNOWN: '来源未知',
  }[profile] || '加载中'
})

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadFilters()])
  await store.loadSchools()
})
</script>
