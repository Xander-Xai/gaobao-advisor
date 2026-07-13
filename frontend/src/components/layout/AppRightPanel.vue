<template>
  <div class="right-panel">
    <h3 class="panel-title">考生画像</h3>
    <div v-if="Object.keys(chat.slots).length" class="slot-list">
      <div
        v-for="(v, k) in chat.slots"
        :key="k"
        class="slot-item"
        v-show="slotDisplayValue(v)"
      >
        <span class="slot-label">{{ SLOT_LABELS[k] || k }}</span>
        <span class="slot-value">{{ slotDisplayValue(v) }}</span>
      </div>
    </div>
    <p v-else class="slot-empty">对话后将显示考生画像</p>
  </div>
</template>

<script setup>
import { useChatStore } from '../../stores/chat'
const SLOT_LABELS = {
  province: '省份',
  score: '分数',
  score_rank: '分数',
  subject: '选科',
  interest: '专业意向',
  region: '地域偏好',
  family: '家庭背景',
  goal: '核心诉求',
}

const chat = useChatStore()

function slotDisplayValue(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object' && v.value) return v.value
  if (typeof v === 'string') return v
  return ''
}
</script>

<style scoped>
.right-panel {
  width: 280px;
  background: var(--surface);
  border-left: 1px solid var(--border);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
  overflow-y: auto;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--secondary);
}

.slot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.slot-item {
  background: var(--paper);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slot-label {
  font-size: 12px;
  color: var(--muted);
}

.slot-value {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
}

.slot-empty {
  text-align: center;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.6;
  margin-top: 24px;
}
</style>