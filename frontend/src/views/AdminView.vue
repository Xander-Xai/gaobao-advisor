<template>
  <div class="min-h-screen bg-gray-50 p-8">
    <div class="max-w-3xl mx-auto">
      <header class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-800">⚙️ 管理面板</h1>
          <p class="text-sm text-gray-500 mt-1">服务健康检查 · 实时反映后端状态</p>
        </div>
        <button
          @click="checkNow"
          :disabled="loading"
          class="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {{ loading ? '检查中...' : '🔄 刷新' }}
        </button>
      </header>

      <div v-if="errorMessage" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-sm text-red-700">
        ❌ {{ errorMessage }}
      </div>

      <div v-if="health" class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="bg-white rounded-xl shadow-sm p-5 border-l-4 border-green-500">
          <div class="text-xs text-gray-500 uppercase tracking-wide">服务状态</div>
          <div class="text-2xl font-bold text-gray-800 mt-2">
            {{ health.status === 'ok' ? '✅ 正常' : '⚠️ 异常' }}
          </div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-5 border-l-4 border-blue-500">
          <div class="text-xs text-gray-500 uppercase tracking-wide">数据库</div>
          <div class="text-2xl font-bold text-gray-800 mt-2">
            {{ health.database === 'connected' ? '🟢 已连接' : '🔴 断开' }}
          </div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-5 border-l-4 border-amber-500">
          <div class="text-xs text-gray-500 uppercase tracking-wide">版本</div>
          <div class="text-2xl font-mono font-bold text-gray-800 mt-2">
            v{{ health.version }}
          </div>
        </div>
      </div>

      <div v-else-if="!loading && !errorMessage" class="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
        点击右上角"刷新"获取健康状态
      </div>

      <div class="mt-8 bg-white rounded-xl shadow-sm p-5">
        <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">已对接后端模块</h2>
        <ul class="space-y-1 text-sm text-gray-700">
          <li>📡 <strong>chat</strong> — SSE 流式对话 + 反馈/金句</li>
          <li>📚 <strong>data</strong> — 院校 / 分数线 / 招生计划</li>
          <li>🧠 <strong>knowledge</strong> — RAG 搜索 + 专家语录</li>
          <li>👤 <strong>profile</strong> — 用户画像（7 字段 + 灵魂提问）</li>
          <li>🎤 <strong>voice</strong> — WebSocket 实时语音 (ASR→Graph→TTS)</li>
          <li>📄 <strong>report</strong> — 报告生成 / HTML / SVG 封面</li>
          <li>🚀 <strong>onboarding</strong> — 3 步引导流程</li>
        </ul>
        <p class="text-xs text-gray-400 mt-4">数据来源: <code>server/routes/*.py</code></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { healthAPI } from '../api/client'

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
