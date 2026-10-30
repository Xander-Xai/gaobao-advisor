<template>
  <section class="space-y-4" aria-label="招生数据列表">
    <form class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" @submit.prevent="applyFilters">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <div class="xl:col-span-2">
          <label for="school-q" class="block text-xs font-medium text-slate-500 mb-1">关键词</label>
          <input
            id="school-q"
            v-model="admin.filters.q"
            data-testid="school-keyword"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            placeholder="院校或城市"
          />
        </div>
        <div>
          <label for="school-province" class="block text-xs font-medium text-slate-500 mb-1">省份</label>
          <select
            id="school-province"
            v-model="admin.filters.province"
            data-testid="school-province"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">全部</option>
            <option v-for="item in admin.filterOptions.provinces" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
        <div>
          <label for="school-level" class="block text-xs font-medium text-slate-500 mb-1">层次</label>
          <select
            id="school-level"
            v-model="admin.filters.level"
            data-testid="school-level"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">全部</option>
            <option v-for="item in admin.filterOptions.levels" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
        <div>
          <label for="school-sort" class="block text-xs font-medium text-slate-500 mb-1">排序</label>
          <select
            id="school-sort"
            v-model="admin.filters.sort"
            data-testid="school-sort"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="id">默认</option>
            <option value="name">名称</option>
            <option value="province">省份</option>
            <option value="level">层次</option>
            <option value="ranking">排名</option>
            <option value="score_count">分数记录数</option>
          </select>
        </div>
        <div class="flex items-end gap-2">
          <button
            type="button"
            class="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            data-testid="toggle-order"
            @click="toggleOrder"
          >{{ admin.filters.order === 'asc' ? '升序 ↑' : '降序 ↓' }}</button>
          <button
            type="submit"
            class="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >查询</button>
        </div>
      </div>
      <div class="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>数据来源：SYNTHETIC_DEMO（程序生成，不可用于真实志愿决策）</span>
        <button type="button" class="text-slate-500 underline hover:text-slate-800" @click="resetFilters">重置筛选</button>
      </div>
    </form>

    <div
      v-if="admin.schoolsError"
      role="alert"
      data-testid="schools-error"
      class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-center justify-between gap-4"
    >
      <span>加载院校失败：{{ admin.schoolsError }}</span>
      <button class="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium" @click="admin.loadSchools(admin.schoolPage)">重试</button>
    </div>

    <div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 class="text-sm font-semibold text-slate-700">院校数据 <span class="text-slate-400 font-normal">共 {{ admin.schoolTotal }} 条</span></h2>
        <span class="text-xs text-slate-400">第 {{ admin.schoolPage }} / {{ Math.max(1, admin.schoolPages) }} 页</span>
      </div>

      <div v-if="admin.schoolsLoading" class="space-y-2 p-4" data-testid="schools-loading" aria-busy="true">
        <div v-for="n in 4" :key="n" class="h-10 animate-pulse rounded-lg bg-slate-100"></div>
      </div>

      <div v-else-if="!admin.schools.length" class="p-10 text-center" data-testid="schools-empty">
        <p class="text-sm font-medium text-slate-600">没有匹配的院校</p>
        <p class="mt-1 text-xs text-slate-400">调整关键词、省份或层次后重试</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
          <caption class="sr-only">合成招生院校列表</caption>
          <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" class="px-4 py-2 font-medium">院校</th>
              <th scope="col" class="px-3 py-2 font-medium">省份</th>
              <th scope="col" class="px-3 py-2 font-medium">层次</th>
              <th scope="col" class="px-3 py-2 font-medium">类型</th>
              <th scope="col" class="px-3 py-2 text-right font-medium">排名</th>
              <th scope="col" class="px-3 py-2 text-right font-medium">分数记录</th>
              <th scope="col" class="px-3 py-2 text-right font-medium">最新最低分</th>
              <th scope="col" class="px-4 py-2 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="school in admin.schools" :key="school.id" class="hover:bg-slate-50/80">
              <td class="px-4 py-2.5">
                <div class="font-medium text-slate-800">{{ school.name }}</div>
                <div class="text-[11px] text-slate-400">{{ school.city }} · {{ school.data_source_note ?? '—' }}</div>
              </td>
              <td class="px-3 py-2.5 text-slate-600">{{ school.province }}</td>
              <td class="px-3 py-2.5">
                <span class="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{{ school.level }}</span>
              </td>
              <td class="px-3 py-2.5 text-slate-600">{{ school.school_type }}</td>
              <td class="px-3 py-2.5 text-right font-mono text-slate-700">{{ school.ranking ?? '—' }}</td>
              <td class="px-3 py-2.5 text-right font-mono text-slate-700">{{ school.score_count }}</td>
              <td class="px-3 py-2.5 text-right font-mono text-slate-700">
                {{ school.latest_min_score ?? '—' }}
                <span class="ml-1 text-[11px] text-slate-400">{{ school.latest_year ?? '' }}</span>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  class="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-white"
                  :data-testid="`school-detail-${school.id}`"
                  :aria-label="`查看 ${school.name} 详情`"
                  @click="admin.loadSchool(school.id)"
                >详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between border-t border-slate-200 px-4 py-3">
        <button
          class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40"
          :disabled="admin.schoolPage <= 1 || admin.schoolsLoading"
          @click="admin.loadSchools(admin.schoolPage - 1)"
        >上一页</button>
        <span class="text-xs text-slate-400">每页 10 条</span>
        <button
          class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40"
          :disabled="admin.schoolPage >= admin.schoolPages || admin.schoolsLoading"
          @click="admin.loadSchools(admin.schoolPage + 1)"
        >下一页</button>
      </div>
    </div>

    <aside
      v-if="admin.selectedSchool || admin.detailLoading || admin.detailError"
      class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      aria-label="院校详情"
      data-testid="school-detail"
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <h2 class="text-base font-semibold text-slate-900">{{ admin.selectedSchool?.name ?? '院校详情' }}</h2>
          <p class="text-xs text-slate-500">{{ admin.selectedSchool?.province }} · {{ admin.selectedSchool?.level }} · {{ admin.selectedSchool?.school_type }}</p>
        </div>
        <button class="rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-600" @click="closeDetail">关闭</button>
      </div>

      <p v-if="admin.detailLoading" class="mt-4 text-sm text-slate-500" aria-busy="true">加载详情中…</p>
      <div v-else-if="admin.detailError" role="alert" class="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ admin.detailError }}
        <button v-if="admin.schoolDetailId" class="ml-2 underline" @click="admin.loadSchool(admin.schoolDetailId)">重试</button>
      </div>
      <template v-else-if="admin.selectedSchool">
        <p class="mt-3 text-xs leading-relaxed text-slate-500">{{ admin.selectedSchool.description }}</p>
        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <div>
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">录取分数</h3>
            <div class="max-h-64 overflow-auto rounded-lg border border-slate-200">
              <table class="min-w-full text-xs">
                <thead class="bg-slate-50 text-left text-slate-500">
                  <tr>
                    <th scope="col" class="px-2 py-1.5">专业</th>
                    <th scope="col" class="px-2 py-1.5">年份</th>
                    <th scope="col" class="px-2 py-1.5">科类</th>
                    <th scope="col" class="px-2 py-1.5 text-right">最低</th>
                    <th scope="col" class="px-2 py-1.5 text-right">平均</th>
                    <th scope="col" class="px-2 py-1.5 text-right">最高</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="score in admin.selectedSchool.scores" :key="score.id">
                    <td class="px-2 py-1.5 text-slate-700">{{ score.major_name ?? '院校线' }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ score.year }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ score.subject_type }}</td>
                    <td class="px-2 py-1.5 text-right font-mono">{{ score.min_score ?? '—' }}</td>
                    <td class="px-2 py-1.5 text-right font-mono">{{ score.avg_score ?? '—' }}</td>
                    <td class="px-2 py-1.5 text-right font-mono">{{ score.max_score ?? '—' }}</td>
                  </tr>
                  <tr v-if="!admin.selectedSchool.scores.length">
                    <td colspan="6" class="px-2 py-4 text-center text-slate-400">暂无分数记录</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">招生计划</h3>
            <div class="max-h-64 overflow-auto rounded-lg border border-slate-200">
              <table class="min-w-full text-xs">
                <thead class="bg-slate-50 text-left text-slate-500">
                  <tr>
                    <th scope="col" class="px-2 py-1.5">专业</th>
                    <th scope="col" class="px-2 py-1.5">年份</th>
                    <th scope="col" class="px-2 py-1.5">省份</th>
                    <th scope="col" class="px-2 py-1.5 text-right">计划</th>
                    <th scope="col" class="px-2 py-1.5">选科</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">
                  <tr v-for="plan in admin.selectedSchool.plans" :key="plan.id">
                    <td class="px-2 py-1.5 text-slate-700">{{ plan.major_name ?? '—' }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ plan.year }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ plan.province }}</td>
                    <td class="px-2 py-1.5 text-right font-mono">{{ plan.plan_count ?? '—' }}</td>
                    <td class="px-2 py-1.5 text-slate-500">{{ plan.subject_requirement ?? '—' }}</td>
                  </tr>
                  <tr v-if="!admin.selectedSchool.plans.length">
                    <td colspan="5" class="px-2 py-4 text-center text-slate-400">暂无招生计划</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()

function applyFilters(): void {
  void admin.loadSchools(1)
}

function resetFilters(): void {
  admin.filters.q = ''
  admin.filters.province = ''
  admin.filters.level = ''
  admin.filters.sort = 'id'
  admin.filters.order = 'asc'
  void admin.loadSchools(1)
}

function toggleOrder(): void {
  admin.filters.order = admin.filters.order === 'asc' ? 'desc' : 'asc'
  void admin.loadSchools(1)
}

function closeDetail(): void {
  admin.selectedSchool = null
}
</script>
