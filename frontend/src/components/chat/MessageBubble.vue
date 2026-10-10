<template>
  <div :class="['msg-row', message.role === 'user' ? 'msg-user' : 'msg-ai']">
    <!-- AI Avatar -->
    <div v-if="message.role === 'assistant'" class="ai-avatar">顾</div>

    <div :class="['bubble', message.role === 'user' ? 'bubble-user' : 'bubble-ai']">
      <div v-html="renderedContent" />

      <!-- Feedback bar (assistant only) -->
      <div
        v-if="message.role === 'assistant' && message.messageIndex >= 0"
        class="feedback-bar"
      >
        <span class="fb-label">有帮助吗？</span>
        <button
          @click="sendFeedback('helpful')"
          :class="['fb-btn', feedback === 'helpful' ? 'fb-helpful' : '']"
          :title="feedback === 'helpful' ? '已标记有帮助' : '有帮助'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/></svg>
        </button>
        <button
          @click="sendFeedback('not_helpful')"
          :class="['fb-btn', feedback === 'not_helpful' ? 'fb-unhelpful' : '']"
          :title="feedback === 'not_helpful' ? '已标记没帮助' : '没帮助'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"/></svg>
        </button>
        <button
          @click="extractHighlight"
          :disabled="highlighted"
          :class="['fb-btn fb-star', highlighted ? 'fb-starred' : '']"
          :title="highlighted ? '已收藏' : '收藏金句'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" :fill="highlighted ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
        </button>

        <!-- quality grade badge -->
        <span v-if="qualityBadgeText" :class="['quality-badge', qualityBadgeClass]">{{ qualityBadgeText }}</span>

        <!-- rewritten indicator -->
        <span v-if="message.rewritten" class="rewritten-badge">已优化</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { renderMarkdown } from '../../utils/sanitize'
import { feedbackAPI, highlightAPI } from '../../api/client'
import { useChatStore } from '../../stores/chat'

const props = defineProps({ message: Object })
const chatStore = useChatStore()
const feedback = ref(null)
const highlighted = ref(false)

const renderedContent = computed(() => {
  return renderMarkdown(props.message.content || '')
})

const qualityBadgeClass = computed(() => {
  const grade = props.message.qualityGrade
  if (grade === 'excellent') return 'quality-excellent'
  if (grade === 'pass') return 'quality-pass'
  if (grade === 'fail') return 'quality-fail'
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
    token: chatStore.sessionToken,
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
    token: chatStore.sessionToken,
  })
  if (error) {
    console.error('Highlight failed:', error.message)
    return
  }
  highlighted.value = true
}
</script>

<style scoped>
.msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.msg-user {
  justify-content: flex-end;
  max-width: 72%;
  margin-left: auto;
}

.msg-ai {
  max-width: 78%;
}

.ai-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: var(--red);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  font-family: var(--font-display);
}

.bubble {
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.65;
  font-family: var(--font-body);
}

.bubble-user {
  background: var(--red);
  color: white;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  box-shadow: 0 1px 3px rgba(212, 49, 46, 0.15);
}

.bubble-ai {
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
  box-shadow: var(--shadow-card);
}

/* Feedback Bar */
.feedback-bar {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
  flex-wrap: wrap;
}

.fb-label {
  font-size: 11px;
  color: var(--muted);
  margin-right: 4px;
}

.fb-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  background: transparent;
  transition: all var(--motion-fast) var(--ease-smooth);
}

.fb-btn:hover {
  background: var(--border);
  color: var(--secondary);
}

.fb-helpful {
  color: var(--success);
  background: var(--success-light);
}

.fb-unhelpful {
  color: var(--red);
  background: var(--red-light);
}

.fb-starred {
  color: var(--gold);
}

.quality-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 500;
  margin-left: auto;
}

.quality-excellent {
  background: var(--success-light);
  color: var(--success);
}

.quality-pass {
  background: var(--gold-light);
  color: var(--gold-dark);
}

.quality-fail {
  background: var(--red-light);
  color: var(--red);
}

.rewritten-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 500;
  background: var(--red-light);
  color: var(--red);
}
</style>