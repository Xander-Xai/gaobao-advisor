<template>
  <div class="subtitle-area">
    <div v-if="userText" class="subtitle-user">{{ userText }}</div>
    <div v-if="assistantText" class="subtitle-ai">{{ assistantText }}</div>
    <div v-if="!userText && !assistantText" class="subtitle-empty">点击下方按钮开始语音对话</div>
  </div>
</template>

<script setup>
defineProps({
  userText: String,
  assistantText: String,
  phase: String,
})
</script>

<style scoped>
.subtitle-area {
  min-height: 72px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.subtitle-user {
  font-size: 14px;
  line-height: 1.6;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--red-light);
  color: var(--red);
  text-align: right;
}

.subtitle-ai {
  font-size: 14px;
  line-height: 1.6;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.04);
  color: var(--ink);
  text-align: left;
}

.subtitle-empty {
  color: var(--muted);
  font-size: 14px;
  text-align: center;
  margin-top: 24px;
}
</style>