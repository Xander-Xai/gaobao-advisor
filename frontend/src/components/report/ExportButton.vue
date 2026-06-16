<template>
  <div class="export-buttons">
    <button @click="exportHTML" class="btn btn-primary">📄 导出 HTML</button>
    <button @click="exportCover" class="btn btn-secondary">🖼️ 下载封面</button>
  </div>
</template>

<script setup>
const props = defineProps({ reportId: { type: String, required: true } })
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
function exportHTML() { window.open(`${API_BASE}/report/${props.reportId}/html`, '_blank') }
function exportCover() { window.open(`${API_BASE}/report/${props.reportId}/cover.svg`, '_blank') }
</script>

<style scoped>
.export-buttons { display: flex; gap: 12px; justify-content: center; padding: 20px; }
.btn { padding: 10px 24px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: all 0.2s; }
.btn-primary { background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); color: #8B0000; font-weight: bold; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(255, 165, 0, 0.4); }
.btn-secondary { background: white; color: #8B0000; border: 2px solid #8B0000; }
.btn-secondary:hover { background: #8B0000; color: white; }
</style>