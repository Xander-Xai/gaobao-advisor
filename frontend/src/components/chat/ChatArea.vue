<template>
  <div ref="container" class="chat-area">
    <!-- Welcome screen -->
    <div v-if="!messages.length" class="welcome-screen">
      <div class="welcome-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="M16 8.2C16 7 15 6 13.8 6h-.4C12 6 11 7 11 8.2v2.3h5v-2.3Z"/><path d="M11 8.2c0-1.2 1-2.2 2.2-2.2h.4C14.8 6 16 7 16 8.2V11"/><path d="M11 11h5v4a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-4Z"/></svg>
      </div>
      <h1>助力每一个梦想</h1>
      <p>我是你的 AI 高考志愿顾问。告诉我你的省份、分数和意向，我来帮你分析。</p>
      <p class="welcome-hint">试试说："我是山东考生，624分，想学计算机"</p>
    </div>

    <!-- Messages -->
    <MessageBubble
      v-for="(msg, i) in messages"
      :key="i"
      :message="{...msg, messageIndex: msg.messageIndex ?? i, sessionId: msg.sessionId || chat.currentSessionId}"
    />

    <!-- Typing indicator -->
    <div v-if="isStreaming" class="typing-indicator-wrapper">
      <div class="ai-avatar-mini">顾</div>
      <div class="typing-dots">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { useChatStore } from '../../stores/chat'
import MessageBubble from './MessageBubble.vue'
const chat = useChatStore()
const container = ref(null)
const messages = computed(() => chat.messages)
const isStreaming = computed(() => chat.isStreaming)
watch(() => messages.value.length, async () => {
  await nextTick()
  container.value?.scrollTo({ top: container.value.scrollHeight, behavior: 'smooth' })
})
</script>

<style scoped>
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Welcome */
.welcome-screen {
  text-align: center;
  padding: 48px 20px;
  max-width: 480px;
  margin: auto;
}

.welcome-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  background: var(--red-light);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-screen h1 {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--ink);
}

.welcome-screen p {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 4px;
}

.welcome-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--disabled);
}

/* Typing indicator */
.typing-indicator-wrapper {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ai-avatar-mini {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--red);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-display);
  flex-shrink: 0;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--muted);
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}
</style>
