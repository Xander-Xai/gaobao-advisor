<template>
  <main class="min-h-screen bg-slate-50 px-4 py-8 text-slate-800 sm:px-8">
    <div class="mx-auto max-w-6xl space-y-6">
      <header class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-widest text-blue-700">Gaobao Advisor / Data Workbench</p>
          <h1 class="mt-2 text-3xl font-bold">运行状态与院校数据</h1>
          <p class="mt-2 text-sm text-slate-500">公开演示数据 · 只读工作台 · 不代表管理员权限</p>
        </div>
        <router-link to="/" class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-100">
          返回 AI 对话
        </router-link>
      </header>

      <section aria-labelledby="health-title" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="health-title" class="text-lg font-semibold">服务健康</h2>
            <p class="mt-1 text-xs text-slate-500">来自 GET /api/v1/health 的实时响应</p>
          </div>
          <button type="button" @click="refreshHealth" :disabled="healthLoading"
            class="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50">
            {{ healthLoading ? '检查中…' : '刷新健康状态' }}
          </button>
        </div>
        <p v-if="healthError" role="alert" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {{ healthError }}
        </p>
        <p v-if="healthLoading && !health" role="status" class="mt-4 text-sm text-slate-500">正在读取状态…</p>
        <div v-if="health" class="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-live="polite">
          <div class="rounded-xl bg-slate-50 p-4">
            <div class="text-xs text-slate-500">服务</div>
            <div class="mt-2 font-semibold">{{ health.status === 'ok' ? '正常' : '降级' }}</div>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <div class="text-xs text-slate-500">数据库</div>
            <div class="mt-2 font-semibold">{{ health.database === 'connected' ? '已连接' : '未连接' }}</div>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <div class="text-xs text-slate-500">RAG</div>
            <div class="mt-2 font-semibold">{{ health.optional_services.rag?.state || '未报告' }}</div>
          </div>
          <div class="rounded-xl bg-slate-50 p-4">
            <div class="text-xs text-slate-500">版本</div>
            <div class="mt-2 font-mono font-semibold">{{ health.version }}</div>
          </div>
        </div>
        <p v-if="health" class="mt-4 text-xs text-slate-500">
          数据环境：{{ health.data_profile }} · 降级模块：{{ health.degraded_services.join('、') || '无' }}
          <span v-if="health.optional_services.rag?.reason"> · RAG 原因：{{ health.optional_services.rag.reason }}</span>
        </p>
      </section>

      <section aria-labelledby="schools-title" class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="mb-5">
          <h2 id="schools-title" class="text-lg font-semibold">院校查询</h2>
          <p class="mt-1 text-xs text-slate-500">
            对接 GET /api/v1/data/schools，按名称检索或按省份、层次游标分页。列表不可编辑。
          </p>
        </div>
        <form class="grid grid-cols-1 items-end gap-3 sm:grid-cols-4" @submit.prevent="applyFilters">
          <label class="block text-sm">
            <span class="mb-1 block text-slate-600">学校名称</span>
            <input v-model.trim="form.schoolName" type="search" name="schoolName" placeholder="精确或关键词查询"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:outline-blue-600" />
          </label>
          <label class="block text-sm">
            <span class="mb-1 block text-slate-600">省份</span>
            <input v-model.trim="form.province" type="text" name="province" placeholder="例如：广东"
              class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:outline-blue-600" />
          </label>
          <label class="block text-sm">
            <span class="mb-1 block text-slate-600">层次</span>
            <select v-model="form.level" name="level" class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2">
              <option value="">全部</option>
              <option value="985">985</option>
              <option value="211">211</option>
              <option value="双一流">双一流</option>
              <option value="普通">普通</option>
            </select>
          </label>
          <button type="submit" :disabled="schoolLoading"
            class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50">
            {{ schoolLoading ? '查询中…' : '查询院校' }}
          </button>
        </form>
        <p v-if="form.schoolName" class="mt-3 text-xs text-amber-700">
          使用学校名称时，后端返回单校匹配结果；省份、层次及分页不参与该检索。
        </p>
        <p v-if="schoolError" role="alert" class="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {{ schoolError }}
          <button type="button" @click="loadSchools" class="ml-2 underline">重试</button>
        </p>
        <div class="mt-5 overflow-x-auto rounded-lg border border-slate-200">
          <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <caption class="sr-only">院校查询结果</caption>
            <thead class="bg-slate-50 text-slate-600">
              <tr>
                <th scope="col" class="px-4 py-3 font-semibold">院校</th>
                <th scope="col" class="px-4 py-3 font-semibold">省份 / 城市</th>
                <th scope="col" class="px-4 py-3 font-semibold">层次</th>
                <th scope="col" class="px-4 py-3 font-semibold">类型</th>
                <th scope="col" class="px-4 py-3 font-semibold">排名</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="school in schools" :key="school.id" class="hover:bg-slate-50">
                <td class="px-4 py-3 font-medium">{{ school.name }}</td>
                <td class="px-4 py-3">{{ school.province }} / {{ school.city || '未标注' }}</td>
                <td class="px-4 py-3">{{ school.level }}</td>
                <td class="px-4 py-3">{{ school.school_type }}</td>
                <td class="px-4 py-3">{{ school.ranking ?? '—' }}</td>
              </tr>
              <tr v-if="!schoolLoading && !schoolError && schools.length === 0">
                <td colspan="5" class="px-4 py-10 text-center text-slate-500">暂无符合条件的院校</td>
              </tr>
              <tr v-if="schoolLoading">
                <td colspan="5" class="px-4 py-10 text-center text-slate-500">正在加载数据…</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mt-4 flex items-center justify-between gap-3">
          <p class="text-sm text-slate-500" role="status" aria-live="polite">
            第 {{ pageIndex + 1 }} 页 · 本页 {{ schools.length }} 条
            <span v-if="nameSearch">（名称单次查询）</span>
          </p>
          <div class="flex gap-2">
            <button type="button" @click="previousPage"
              :disabled="schoolLoading || pageIndex === 0 || nameSearch"
              class="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">上一页</button>
            <button type="button" @click="nextPage"
              :disabled="schoolLoading || !hasMore || !nextCursor || nameSearch"
              class="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:opacity-40">下一页</button>
          </div>
        </div>
      </section>
      <p class="text-xs leading-5 text-slate-500">
        提示：本项目公开仓库使用 SYNTHETIC_DEMO 合成数据。此工作台不具备管理员登录、RBAC 或数据修改权限，
        不应被用于真实高考填报决策。
      </p>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { fetchHealth, fetchSchools } from '../api/admin'
import type { HealthSnapshot, School, SchoolFilters } from '../api/admin'

const health = ref<HealthSnapshot | null>(null)
const healthLoading = ref(false)
const healthError = ref('')
const form = reactive<SchoolFilters>({ schoolName: '', province: '', level: '' })
const applied = ref<SchoolFilters>({ schoolName: '', province: '', level: '' })
const schools = ref<School[]>([])
const schoolLoading = ref(false)
const schoolError = ref('')
const pageIndex = ref(0)
const cursors = ref<(string | null)[]>([null])
const nextCursor = ref<string | null>(null)
const hasMore = ref(false)
const nameSearch = ref(false)

let healthController: AbortController | undefined
let schoolController: AbortController | undefined

function message(error: unknown): string {
  return error instanceof Error ? error.message : '服务请求失败'
}

async function refreshHealth() {
  healthController?.abort()
  const controller = new AbortController()
  healthController = controller
  healthLoading.value = true
  healthError.value = ''
  try {
    health.value = await fetchHealth(controller.signal)
  } catch (error) {
    if (controller.signal.aborted) return
    health.value = null
    healthError.value = message(error)
  } finally {
    if (healthController === controller) healthLoading.value = false
  }
}

async function loadSchools() {
  schoolController?.abort()
  const controller = new AbortController()
  schoolController = controller
  schoolLoading.value = true
  schoolError.value = ''
  schools.value = []
  nextCursor.value = null
  hasMore.value = false
  try {
    const page = await fetchSchools(applied.value, cursors.value[pageIndex.value] ?? null, 10, controller.signal)
    if (controller.signal.aborted) return
    schools.value = page.items
    nextCursor.value = page.nextCursor
    hasMore.value = page.hasMore
    nameSearch.value = page.nameSearch
  } catch (error) {
    if (controller.signal.aborted) return
    schoolError.value = message(error)
  } finally {
    if (schoolController === controller) schoolLoading.value = false
  }
}

function applyFilters() {
  applied.value = { ...form }
  pageIndex.value = 0
  cursors.value = [null]
  void loadSchools()
}

function nextPage() {
  if (!hasMore.value || !nextCursor.value || schoolLoading.value || nameSearch.value) return
  cursors.value = [...cursors.value.slice(0, pageIndex.value + 1), nextCursor.value]
  pageIndex.value += 1
  void loadSchools()
}

function previousPage() {
  if (pageIndex.value === 0 || schoolLoading.value || nameSearch.value) return
  pageIndex.value -= 1
  cursors.value = cursors.value.slice(0, pageIndex.value + 1)
  void loadSchools()
}

onMounted(() => {
  void refreshHealth()
  void loadSchools()
})
onBeforeUnmount(() => {
  healthController?.abort()
  schoolController?.abort()
})
</script>
