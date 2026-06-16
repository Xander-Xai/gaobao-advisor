<template>
  <div ref="container" class="flex-1 p-4 space-y-4">
    <div v-if="!messages.length" class="flex items-center justify-center h-full text-gray-400">
      <div class="text-center">
        <div class="text-4xl mb-4">&#x1F393;</div>
        <p class="text-lg">您好！我是高考志愿AI顾问</p>
        <p class="text-sm mt-2">请告诉我您的省份、分数和兴趣方向</p>
      </div>
    </div>
    <MessageBubble v-for="(msg, i) in messages" :key="i" :message="{...msg, messageIndex: i, sessionId: chat.sessionId}" />
    <div v-if="isStreaming" class="flex items-center gap-2 text-gray-400 text-sm pl-12">
      <span class="animate-pulse">&#x25CF;</span> 正在思考...
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../../stores/chat'
import MessageBubble from './MessageBubble.vue'
const chat = useChatStore()
const container = ref(null)
const messages = chat.messages
const isStreaming = chat.isStreaming
watch(() => messages.length, async () => {
  await nextTick()
  container.value?.scrollTo({ top: container.value.scrollHeight, behavior: 'smooth' })
})
</script>
