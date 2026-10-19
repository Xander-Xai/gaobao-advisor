<template>
  <div class="export-buttons">
    <button @click="exportHTML" class="btn btn-primary">📄 导出 HTML</button>
    <button @click="exportCover" class="btn btn-secondary">🖼️ 下载封面</button>
  </div>
</template>

<script setup>
import { reportAPI } from '../../api/client'

const props = defineProps({
  reportId: { type: String, required: true },
  sessionToken: { type: String, default: null },
})

function exportHTML() {
  reportAPI.exportHTML(props.reportId, props.sessionToken).catch(err => {
    console.error('HTML export failed:', err.message)
  })
}
function exportCover() {
  reportAPI.exportCover(props.reportId, props.sessionToken).catch(err => {
    console.error('Cover export failed:', err.message)
  })
}
</script>

<style scoped>
.export-buttons { display: flex; gap: 12px; justify-content: center; padding: 20px; }
.btn { padding: 10px 24px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; transition: all 0.2s; }
.btn-primary { background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); color: #8B0000; font-weight: bold; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(255, 165, 0, 0.4); }
.btn-secondary { background: white; color: #8B0000; border: 2px solid #8B0000; }
.btn-secondary:hover { background: #8B0000; color: white; }
</style>