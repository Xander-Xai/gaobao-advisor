<template>
  <div class="input-bar">
    <div class="input-wrapper">
      <textarea
        v-model="input"
        @keydown.enter.exact.prevent="send"
        placeholder="输入你的高考问题..."
        rows="1"
        :disabled="chat.isStreaming"
        class="input-textarea"
      />
      <div class="input-actions">
        <button
          @click="voiceStore.open()"
          class="icon-btn"
          title="语音通话"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        </button>
        <button
          @click="send"
          :disabled="!input.trim() || chat.isStreaming"
          class="btn-send"
          title="发送"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useChatStore } from '../../stores/chat'
import { useVoiceStore } from '../../stores/voice'
const chat = useChatStore()
const voiceStore = useVoiceStore()
const input = ref('')
async function send() {
  const text = input.value.trim()
  if (!text || chat.isStreaming) return
  input.value = ''
  await chat.sendMessage(text)
}
</script>

<style scoped>
.input-bar {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--paper);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 8px 8px 8px 16px;
  transition: border-color var(--motion-fast), box-shadow var(--motion-fast);
  max-width: 800px;
  margin: 0 auto;
}

.input-wrapper:focus-within {
  border-color: var(--red);
  box-shadow: 0 0 0 3px rgba(212, 49, 46, 0.12);
}

.input-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font: 400 14px/1.5 var(--font-body);
  color: var(--ink);
  resize: none;
  min-height: 22px;
  max-height: 120px;
}

.input-textarea::placeholder {
  color: var(--muted);
}

.input-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  transition: all var(--motion-fast) var(--ease-smooth);
}

.icon-btn:hover {
  background: var(--border);
  color: var(--secondary);
}

.btn-send {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--red);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--motion-fast) var(--ease-smooth);
}

.btn-send:hover {
  background: var(--red-dark);
}

.btn-send:disabled {
  background: var(--disabled);
  cursor: not-allowed;
}
</style>