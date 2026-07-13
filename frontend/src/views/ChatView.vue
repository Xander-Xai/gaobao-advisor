<template>
  <div class="chat-layout">
    <AppSidebar />
    <div class="chat-main">
      <AppHeader />
      <ChatArea />
      <MessageInput />
      <div v-if="chatStore.messages.length > 0 && chatStore.sessionToken" class="report-actions">
        <button @click="handleGenerateReport" :disabled="reportStore.loading" class="btn-generate-report">
          <svg v-if="!reportStore.loading" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span v-else class="spinner-mini"></span>
          {{ reportStore.loading ? '生成中...' : '生成报告' }}
        </button>
      </div>
    </div>
    <AppRightPanel />
    <VoiceModal :visible="voiceStore.showModal" />
  </div>
</template>

<script setup>
import AppSidebar from '../components/layout/AppSidebar.vue'
import AppHeader from '../components/layout/AppHeader.vue'
import ChatArea from '../components/chat/ChatArea.vue'
import MessageInput from '../components/chat/MessageInput.vue'
import AppRightPanel from '../components/layout/AppRightPanel.vue'
import VoiceModal from '../components/voice/VoiceModal.vue'
import { useVoiceStore } from '../stores/voice'
import { useRouter } from 'vue-router'
import { useReportStore } from '../stores/report'
import { useChatStore } from '../stores/chat'

const voiceStore = useVoiceStore()
const router = useRouter()
const reportStore = useReportStore()
const chatStore = useChatStore()

async function handleGenerateReport() {
  try {
    const result = await reportStore.generateReport(chatStore.currentSessionId)
    if (result?.report_id) {
      router.push({ name: 'report', params: { id: result.report_id } })
    }
  } catch (err) {
    // Error is already shown by reportStore.error
  }
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: var(--paper);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.report-actions { display: flex; justify-content: center; padding: 4px 0; }
.btn-generate-report { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; font: 600 13px var(--font-body); transition: opacity 0.2s; }
.btn-generate-report:hover { opacity: 0.9; }
.btn-generate-report:disabled { opacity: 0.6; cursor: not-allowed; }
.spinner-mini { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.8s linear infinite; }
</style>