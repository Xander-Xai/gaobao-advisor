<template>
  <div class="admin-page">
    <AppHeader />
    <div class="admin-container">
      <header class="admin-header">
        <div>
          <h1 class="page-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            管理面板
          </h1>
          <p class="page-desc">服务健康检查 · 实时反映后端状态</p>
        </div>
        <button
          @click="checkNow"
          :disabled="loading"
          class="btn-refresh"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" :class="{ 'spin': loading }"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          {{ loading ? '检查中...' : '刷新' }}
        </button>
      </header>

      <!-- Error -->
      <div v-if="errorMessage" class="msg-error">
        <span>{{ errorMessage }}</span>
      </div>

      <!-- Health cards -->
      <div v-if="health" class="health-grid">
        <div class="health-card status-ok">
          <div class="card-label">服务状态</div>
          <div class="card-value">{{ health.status === 'ok' ? '正常' : '异常' }}</div>
          <div :class="['status-dot', health.status === 'ok' ? 'dot-green' : 'dot-red']"></div>
        </div>
        <div :class="['health-card', health.database === 'connected' ? 'status-ok' : 'status-error']">
          <div class="card-label">数据库</div>
          <div class="card-value">{{ health.database === 'connected' ? '已连接' : '断开' }}</div>
          <div :class="['status-dot', health.database === 'connected' ? 'dot-green' : 'dot-red']"></div>
        </div>
        <div class="health-card">
          <div class="card-label">版本</div>
          <div class="card-value mono">v{{ health.version }}</div>
        </div>
      </div>

      <div v-else-if="!loading && !errorMessage" class="empty-state">
        点击「刷新」获取健康状态
      </div>

      <!-- Module list -->
      <div class="module-card">
        <h3 class="module-title">已对接后端模块</h3>
        <ul class="module-list">
          <li class="module-item">
            <span class="module-icon" style="color: var(--red);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </span>
            <div><strong>chat</strong> — SSE 流式对话 + 反馈/金句</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--info);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            </span>
            <div><strong>data</strong> — 院校 / 分数线 / 招生计划</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--gold);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>
            </span>
            <div><strong>knowledge</strong> — RAG 搜索 + 专家语录</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--red);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </span>
            <div><strong>profile</strong> — 用户画像（7 字段 + 灵魂提问）</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--info);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
            </span>
            <div><strong>voice</strong> — WebSocket 实时语音 (ASR→Graph→TTS)</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--gold);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            </span>
            <div><strong>report</strong> — 报告生成 / HTML / SVG 封面</div>
          </li>
          <li class="module-item">
            <span class="module-icon" style="color: var(--success);">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            </span>
            <div><strong>onboarding</strong> — 3 步引导流程</div>
          </li>
        </ul>
        <p class="module-footnote">数据来源: <code>server/routes/*.py</code></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { healthAPI } from '../api/client'
import AppHeader from '../components/layout/AppHeader.vue'

const health = ref(null)
const loading = ref(false)
const errorMessage = ref('')

async function checkNow() {
  loading.value = true
  errorMessage.value = ''
  const { data, error } = await healthAPI.check()
  loading.value = false
  if (error) {
    errorMessage.value = `健康检查失败: ${error.message}`
    health.value = null
    return
  }
  health.value = data
}

onMounted(checkNow)
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: var(--paper);
}

.admin-container {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px;
}

.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}

.page-desc {
  font-size: 13px;
  color: var(--muted);
  margin-top: 4px;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 20px;
  background: var(--red);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font: 600 13px var(--font-body);
  cursor: pointer;
  transition: background var(--motion-fast);
}

.btn-refresh:hover {
  background: var(--red-dark);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.msg-error {
  background: var(--red-light);
  border: 1px solid var(--red);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--red);
}

/* Health cards */
.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.health-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  position: relative;
}

.status-ok { border-left: 3px solid var(--success); }
.status-error { border-left: 3px solid var(--red); }

.card-label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.card-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}

.card-value.mono {
  font-family: var(--font-mono);
  font-weight: 600;
}

.status-dot {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-green { background: var(--success); }
.dot-red { background: var(--red); }

.empty-state {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 48px 20px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 24px;
}

/* Module list */
.module-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-card);
}

.module-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--secondary);
  margin-bottom: 16px;
}

.module-list {
  list-style: none;
  padding: 0;
}

.module-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  color: var(--secondary);
  line-height: 1.6;
}

.module-item:last-child {
  border-bottom: none;
}

.module-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.module-footnote {
  margin-top: 12px;
  font-size: 12px;
  color: var(--muted);
}

.module-footnote code {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--secondary);
}
</style>