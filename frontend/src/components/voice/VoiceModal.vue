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
      <div class="absolute bottom-0 left-0 right-0 p-6 flex justify-center gap-6">
        <button
          @click="isMuted = !isMuted"
          class="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center text-white hover:bg-white/20 text-xl"
        >
          {{ isMuted ? '🔇' : '🎤' }}
        </button>
        <button
          @click="voiceStore.close()"
          class="w-12 h-12 rounded-full bg-red-500/80 flex items-center justify-center text-white hover:bg-red-600 text-xl"
        >
          📞
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useVoice } from '../../composables/useVoice'
import { useVoiceStore } from '../../stores/voice'
import VoiceRipple from './VoiceRipple.vue'
import LiveSubtitle from './LiveSubtitle.vue'

const props = defineProps({
  visible: Boolean,
  sessionId: String,
  scene: String,
})

const voiceStore = useVoiceStore()
const { isConnected, isMuted, phase, liveUserText, liveAssistantText, connect, disconnect } = useVoice()

const statusText = computed(() => {
  const map = {
    idle: '准备就绪',
    listening: '正在聆听...',
    thinking: '思考中...',
    speaking: '正在回答...',
  }
  return map[phase.value] || '准备就绪'
})
</script>
