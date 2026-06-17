<template>
  <div :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
    <div :class="['max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
      message.role === 'user' ? 'bg-blue-600 text-white rounded-br-sm' : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm']">
      <div v-html="renderedContent" />
      <!-- feedback -->
      <div v-if="message.role === 'assistant' && message.messageIndex >= 0" class="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100">
        <span class="text-xs text-gray-400">这条回答对你有帮助吗？</span>
        <button @click="sendFeedback('helpful')" :class="['text-xs px-2 py-0.5 rounded transition', feedback === 'helpful' ? 'bg-green-100 text-green-600' : 'text-gray-400 hover:text-green-500']">👍 有帮助</button>
        <button @click="sendFeedback('not_helpful')" :class="['text-xs px-2 py-0.5 rounded transition', feedback === 'not_helpful' ? 'bg-red-100 text-red-500' : 'text-gray-400 hover:text-red-500']">👎 没帮助</button>
        <!-- quality grade badge -->
        <span v-if="qualityBadgeText" :class="['text-xs px-1.5 py-0.5 rounded font-medium', qualityBadgeClass]">{{ qualityBadgeText }}</span>
        <!-- rewritten indicator -->
        <span v-if="message.rewritten" class="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-500 font-medium">已优化</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { renderMarkdown } from '../../utils/sanitize'

const props = defineProps({ message: Object })
const feedback = ref(null)

const renderedContent = computed(() => {
  return renderMarkdown(props.message.content || '')
})

const qualityBadgeClass = computed(() => {
  const grade = props.message.qualityGrade
  if (grade === 'excellent') return 'bg-green-100 text-green-600'
  if (grade === 'pass') return 'bg-yellow-100 text-yellow-600'
  if (grade === 'fail') return 'bg-red-100 text-red-500'
  return ''
})

const qualityBadgeText = computed(() => {
  const grade = props.message.qualityGrade
  if (grade === 'excellent') return '优秀'
  if (grade === 'pass') return '合格'
  if (grade === 'fail') return '需优化'
  return ''
})

async function sendFeedback(rating) {
  if (feedback.value === rating) return
  feedback.value = rating
  try {
    await fetch('/api/v1/chat/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: props.message.sessionId || '',
        message_index: props.message.messageIndex || 0,
        rating,
      }),
    })
  } catch (e) {
    console.error('Feedback failed:', e)
  }
}
</script>
