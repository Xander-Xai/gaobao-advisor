<template>
  <div class="border-t border-gray-200 bg-white p-4">
    <div class="flex items-end gap-3 max-w-4xl mx-auto">
      <textarea v-model="input" @keydown.enter.exact.prevent="send"
        placeholder="请输入您的省份、分数和兴趣方向..."
        class="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        rows="1" :disabled="chat.isStreaming" />
      <button @click="send" :disabled="!input.trim() || chat.isStreaming"
        class="rounded-xl bg-blue-600 px-5 py-3 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
        发送
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useChatStore } from '../../stores/chat'
const chat = useChatStore()
const input = ref('')
async function send() {
  const text = input.value.trim()
  if (!text || chat.isStreaming) return
  input.value = ''
  await chat.sendMessage(text)
}
</script>
