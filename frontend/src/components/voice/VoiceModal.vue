<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="voice-modal"
    >
      <div class="voice-header">
        <div class="voice-status">{{ statusText }}</div>
        <div class="voice-advisor-name">志愿顾问</div>
      </div>

      <!-- Ripple -->
      <div class="ripple-area">
        <VoiceRipple :active="phase === 'speaking' || phase === 'listening'" />
        <div class="ripple-center">
          <svg v-if="phase === 'speaking' || phase === 'listening'" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        </div>
      </div>

      <LiveSubtitle
        :user-text="liveUserText"
        :assistant-text="liveAssistantText"
        :phase="phase"
      />

      <!-- Auth warning -->
      <div
        v-if="!canConnect"
        class="auth-warning"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        请先发送一条消息获取 session token，再启用语音模式
      </div>

      <!-- Controls -->
      <div class="voice-controls">
        <button
          @click="isMuted = !isMuted"
          class="vc-btn vc-secondary"
          :disabled="!isConnected"
          :title="isMuted ? '取消静音' : '静音'"
        >
          <svg v-if="isMuted" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        </button>

        <button
          v-if="!isConnected"
          @click="onConnect"
          :disabled="!canConnect"
          class="vc-btn vc-primary"
          :title="canConnect ? '连接语音' : '需要 session token'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        </button>
        <button
          v-else
          @click="disconnect(); voiceStore.close()"
          class="vc-btn vc-danger"
          title="挂断"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
        </button>
      </div>

      <div class="voice-hint">点击麦克风开始语音对话</div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useVoice } from '../../composables/useVoice'
import { useVoiceStore } from '../../stores/voice'
import { useChatStore } from '../../stores/chat'
import VoiceRipple from './VoiceRipple.vue'
import LiveSubtitle from './LiveSubtitle.vue'

const props = defineProps({
  visible: Boolean,
  sessionId: String,
  scene: String,
})

const voiceStore = useVoiceStore()
const chatStore = useChatStore()
const { isConnected, isMuted, phase, liveUserText, liveAssistantText, connect, disconnect } = useVoice()

const canConnect = computed(() => Boolean(chatStore.sessionToken))
const effectiveSessionId = computed(() => props.sessionId || chatStore.currentSessionId)
const effectiveScene = computed(() => props.scene || 'gaokao')

const statusText = computed(() => {
  if (!canConnect.value) return '请先发送一条消息'
  const map = {
    idle: '准备就绪',
    listening: '正在聆听...',
    thinking: '思考中...',
    speaking: '正在回答...',
  }
  return map[phase.value] || '准备就绪'
})

function onConnect() {
  if (!canConnect.value) return
  connect(effectiveSessionId.value, effectiveScene.value, chatStore.sessionToken)
}

watch(
  () => voiceStore.showModal,
  (open) => {
    if (!open && isConnected.value) disconnect()
  }
)
</script>

<style scoped>
.voice-modal {
  position: fixed;
  bottom: 24px;
  right: 32px;
  width: 360px;
  background: linear-gradient(160deg, var(--paper) 0%, var(--surface) 50%, var(--elevated) 100%);
  border-radius: var(--radius-xl);
  box-shadow: 0 16px 60px rgba(0, 0, 0, 0.5);
  padding: 32px 24px 24px;
  z-index: 50;
  user-select: none;
  overflow: hidden;
}

.voice-header {
  text-align: center;
}

.voice-status {
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 4px;
}

.voice-advisor-name {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
}

.ripple-area {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 24px 0;
  position: relative;
  height: 100px;
}

.ripple-center {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--red) 0%, var(--red-dark) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  box-shadow: 0 0 30px rgba(232, 84, 80, 0.3);
  position: relative;
  z-index: 2;
}

.auth-warning {
  margin: 0 0 16px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(212, 49, 46, 0.1);
  border: 1px solid rgba(232, 84, 80, 0.3);
  color: #e85450;
  font-size: 12px;
  line-height: 1.5;
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.voice-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.vc-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--motion-fast) var(--ease-smooth);
}

.vc-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: var(--secondary);
}

.vc-secondary:hover {
  background: rgba(255, 255, 255, 0.14);
  color: var(--ink);
}

.vc-primary {
  background: var(--red);
  color: white;
  box-shadow: 0 4px 16px rgba(232, 84, 80, 0.3);
}

.vc-primary:hover {
  background: var(--red-dark);
  box-shadow: 0 4px 20px rgba(232, 84, 80, 0.4);
}

.vc-danger {
  background: var(--red-dark);
  color: white;
  box-shadow: 0 4px 16px rgba(204, 64, 62, 0.3);
}

.vc-danger:hover {
  background: var(--red-dark);
}

.vc-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-hint {
  text-align: center;
  font-size: 12px;
  color: #6b655b;
  margin-top: 12px;
}
</style>