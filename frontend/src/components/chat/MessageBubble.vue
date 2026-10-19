<template>
  <div :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
    <div :class="['max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
      message.role === 'user' ? 'bg-blue-600 text-white rounded-br-sm' : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm']">
      <div v-html="renderedContent" />
      <!-- stream metadata: errors, degradation, retrieval sources -->
      <div
        v-if="message.error || message.incomplete || message.degraded || (message.sources && message.sources.length) || (message.ragStatus && message.ragStatus.state === 'NO_EVIDENCE')"
        class="mt-2 pt-2 border-t border-gray-100 text-xs flex flex-wrap items-center gap-2"
      >
        <span v-if="message.error || message.incomplete" class="text-red-500">
          ⚠ {{ message.incomplete ? '连接中断，回复可能不完整' : '生成失败' }}
        </span>
        <span v-if="message.degraded" class="text-amber-600">已降级</span>
        <span v-if="message.ragStatus && message.ragStatus.state === 'NO_EVIDENCE'" class="text-gray-400">无匹配证据</span>
        <template v-if="message.sources && message.sources.length">
          <span class="text-gray-400">来源:</span>
          <span v-for="(s, i) in message.sources" :key="i" class="px-1.5 py-0.5 bg-gray-100 rounded text-gray-500">{{ s.source }}</span>
        </template>
      </div>
      <!-- feedback -->
      <div v-if="message.role === 'assistant' && !message.error && !message.incomplete && message.messageIndex >= 0" class="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100 flex-wrap">
        <span class="text-xs text-gray-400">这条回答对你有帮助吗？</span>
        <button @click="sendFeedback('helpful')" :class="['text-xs px-2 py-0.5 rounded transition', feedback === 'helpful' ? 'bg-green-100 text-green-600' : 'text-gray-400 hover:text-green-500']">👍 有帮助</button>
        <button @click="sendFeedback('not_helpful')" :class="['text-xs px-2 py-0.5 rounded transition', feedback === 'not_helpful' ? 'bg-red-100 text-red-500' : 'text-gray-400 hover:text-red-500']">👎 没帮助</button>
        <button
          @click="extractHighlight"
          :disabled="highlighted"
          :class="['text-xs px-2 py-0.5 rounded transition',
            highlighted ? 'bg-amber-100 text-amber-700' : 'text-gray-400 hover:text-amber-500 disabled:opacity-60']"
          title="收藏为金句"
        >⭐ {{ highlighted ? '已收藏' : '收藏金句' }}</button>
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
import { feedbackAPI, highlightAPI } from '../../api/client'

const props = defineProps({ message: Object })
const feedback = ref(null)
const highlighted = ref(false)

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
  const { error } = await feedbackAPI.submit({
    sessionId: props.message.sessionId || '',
    messageIndex: props.message.messageIndex || 0,
    rating,
    qualityScoreId: props.message.qualityScoreId,
    token: props.message.sessionToken || null,
  })
  if (error) console.error('Feedback failed:', error.message)
}

async function extractHighlight() {
  if (highlighted.value) return
  const content = String(props.message.content || '').trim()
  if (content.length < 10) return
  const { error } = await highlightAPI.submit({
    sessionId: props.message.sessionId || '',
    content,
    score: 80,
    token: props.message.sessionToken || null,
  })
  if (error) {
    console.error('Highlight failed:', error.message)
    return
  }
  highlighted.value = true
}
</script>
