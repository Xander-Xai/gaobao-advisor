<template>
  <div class="export-actions">
    <button @click="exportHTML" class="btn-export primary">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
      导出 HTML 报告
    </button>
    <button @click="exportCover" class="btn-export secondary">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      下载封面
    </button>
  </div>
</template>

<script setup>
import { useReportStore } from '../../stores/report'
const props = defineProps({ reportId: { type: String, required: true } })
const reportStore = useReportStore()
function exportHTML() { reportStore.exportHTML(props.reportId) }
function exportCover() { reportStore.exportCover(props.reportId) }
</script>

<style scoped>
.export-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 24px;
}

.btn-export {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border-radius: var(--radius-md);
  font: 600 14px var(--font-body);
  cursor: pointer;
  border: none;
  transition: all var(--motion-fast) var(--ease-smooth);
}

.btn-export.primary {
  background: var(--red);
  color: white;
}

.btn-export.primary:hover {
  background: var(--red-dark);
}

.btn-export.secondary {
  background: var(--surface);
  color: var(--secondary);
  border: 1px solid var(--border);
}

.btn-export.secondary:hover {
  border-color: var(--muted);
  color: var(--ink);
}
</style>
