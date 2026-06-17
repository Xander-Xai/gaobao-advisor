<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed bottom-24 right-8 w-[360px] h-[620px] rounded-3xl shadow-2xl overflow-hidden z-50 select-none"
      :style="{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)' }"
    >
      <div class="text-white text-center pt-8 pb-4">
        <div class="w-20 h-20 mx-auto rounded-full bg-blue-500/30 flex items-center justify-center mb-4 relative">
          <VoiceRipple :active="phase === 'speaking'" />
          <span class="text-3xl relative z-10">🎓</span>
        </div>
        <p class="text-sm text-white/60">{{ statusText }}</p>
      </div>
      <LiveSubtitle
        :user-text="liveUserText"
        :assistant-text="liveAssistantText"
        :phase="phase"
      />
      <div
        v-if="!canConnect"
        class="absolute bottom-32 left-6 right-6 p-3 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-100 text-xs text-center"
      >
        ⚠ 请先在对话页发送一条消息获取 session token，再启用语音模式
      </div>
      <div class="absolute bottom-0 left-0 right-0 p-6 flex justify-center gap-6">
        <button
          @click="isMuted = !isMuted"
          class="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center text-white hover:bg-white/20 text-xl"
          :disabled="!isConnected"
        >
          {{ isMuted ? '🔇' : '🎤' }}
        </button>
        <button
          v-if="!isConnected"
          @click="onConnect"
          :disabled="!canConnect"
          class="w-12 h-12 rounded-full bg-green-500/80 flex items-center justify-center text-white hover:bg-green-600 text-xl disabled:opacity-40 disabled:cursor-not-allowed"
          :title="canConnect ? '连接语音' : '需要 session token'"
        >
          📲
        </button>
        <button
          v-else
          @click="disconnect(); voiceStore.close()"
          class="w-12 h-12 rounded-full bg-red-500/80 flex items-center justify-center text-white hover:bg-red-600 text-xl"
        >
          📞
        </button>
      </div>
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

// Backend rejects ws connections with code 4001 when token is missing.
// The token is delivered only via chat SSE `done` event, so the user
// must send at least one text message before voice mode can authenticate.
const canConnect = computed(() => Boolean(chatStore.sessionToken))
const effectiveSessionId = computed(() => props.sessionId || chatStore.currentSessionId)
const effectiveScene = computed(() => props.scene || 'gaokao')

const statusText = computed(() => {
  if (!canConnect.value) return '请先发送一条消息建立会话'
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

// Auto-disconnect when the modal is closed.
watch(
  () => voiceStore.showModal,
  (open) => {
    if (!open && isConnected.value) disconnect()
  }
)
</script>
