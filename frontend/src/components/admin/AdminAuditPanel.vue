<template>
  <section class="space-y-4" aria-label="操作审计日志">
    <div class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div>
        <h2 class="text-sm font-semibold text-slate-800">操作审计</h2>
        <p class="text-xs text-slate-400">记录操作主体、角色、资源与请求关联 ID；敏感字段在落库前脱敏。</p>
      </div>
      <button class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-600" @click="admin.loadAudit(admin.auditPage)">刷新</button>
    </div>

    <div v-if="admin.auditError" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="audit-error">
      {{ admin.auditError }}
      <button class="ml-2 underline" @click="admin.loadAudit(admin.auditPage)">重试</button>
    </div>

    <div class="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div v-if="admin.auditLoading" class="space-y-2 p-4" aria-busy="true">
        <div v-for="n in 4" :key="n" class="h-9 animate-pulse rounded-lg bg-slate-100"></div>
      </div>
      <div v-else-if="!admin.auditLogs.length" class="p-10 text-center" data-testid="audit-empty">
        <p class="text-sm font-medium text-slate-600">暂无审计记录</p>
        <p class="mt-1 text-xs text-slate-400">创建任务或审核后会在这里留下不可变记录</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-sm">
          <caption class="sr-only">运营操作审计日志</caption>
          <thead class="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th scope="col" class="px-4 py-2 font-medium">时间</th>
              <th scope="col" class="px-3 py-2 font-medium">主体</th>
              <th scope="col" class="px-3 py-2 font-medium">动作</th>
              <th scope="col" class="px-3 py-2 font-medium">资源</th>
              <th scope="col" class="px-3 py-2 font-medium">结果</th>
              <th scope="col" class="px-3 py-2 font-medium">Request ID</th>
              <th scope="col" class="px-4 py-2 font-medium">详情</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="log in admin.auditLogs" :key="log.id" class="align-top hover:bg-slate-50/80">
              <td class="px-4 py-2.5 text-xs text-slate-400">{{ formatTime(log.created_at) }}</td>
              <td class="px-3 py-2.5 text-slate-700">{{ log.actor }}<span class="ml-1 text-[11px] text-slate-400">{{ log.role }}</span></td>
              <td class="px-3 py-2.5 font-mono text-xs text-slate-700">{{ log.action }}</td>
              <td class="px-3 py-2.5 text-xs text-slate-500">{{ log.resource_type }}#{{ log.resource_id }}</td>
              <td class="px-3 py-2.5">
                <span class="rounded-full px-2 py-0.5 text-xs" :class="log.outcome === 'SUCCESS' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'">{{ log.outcome }}</span>
              </td>
              <td class="px-3 py-2.5 font-mono text-[11px] text-slate-500">{{ log.request_id }}</td>
              <td class="px-4 py-2.5 text-xs">
                <details>
                  <summary class="cursor-pointer text-slate-500">查看</summary>
                  <pre class="mt-1 max-w-xs whitespace-pre-wrap break-all rounded bg-slate-50 p-2 text-[11px] text-slate-600">{{ JSON.stringify(log.detail, null, 2) }}</pre>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between border-t border-slate-200 px-4 py-3">
        <button class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40" :disabled="admin.auditPage <= 1" @click="admin.loadAudit(admin.auditPage - 1)">上一页</button>
        <span class="text-xs text-slate-400">共 {{ admin.auditTotal }} 条 · 第 {{ admin.auditPage }} / {{ Math.max(1, admin.auditPages) }} 页</span>
        <button class="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 disabled:opacity-40" :disabled="admin.auditPage >= admin.auditPages" @click="admin.loadAudit(admin.auditPage + 1)">下一页</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}
</script>
