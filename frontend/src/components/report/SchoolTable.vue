<template>
  <div class="school-table">
    <h3>🎯 院校推荐</h3>
    <div v-if="suggestions.length === 0" class="empty"><p>暂无推荐数据，建议继续对话获取详细分析</p></div>
    <div v-else class="school-cards">
      <div v-for="(suggestion, index) in suggestions" :key="index" :class="['school-card', getLevelClass(suggestion)]">
        <div class="card-header"><span class="level-badge">{{ getLevelLabel(suggestion) }}</span></div>
        <p class="suggestion-text">{{ suggestion }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ suggestions: { type: Array, default: () => [] } })
function getLevelClass(text) {
  if (text.includes('冲')) return 'rush'
  if (text.includes('稳')) return 'stable'
  if (text.includes('保')) return 'safe'
  return ''
}
function getLevelLabel(text) {
  if (text.includes('冲')) return '冲'
  if (text.includes('稳')) return '稳'
  if (text.includes('保')) return '保'
  return '荐'
}
</script>

<style scoped>
.school-table { margin: 24px 0; }
.school-table h3 { color: #8B0000; font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #FFD700; }
.school-cards { display: grid; gap: 12px; }
.school-card { padding: 16px; border-radius: 8px; border-left: 4px solid #ccc; background: #f9f9f9; }
.school-card.rush { border-left-color: #DC143C; background: #fff5f5; }
.school-card.stable { border-left-color: #FFD700; background: #fffbf0; }
.school-card.safe { border-left-color: #32CD32; background: #f0fff0; }
.level-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: white; background: #8B0000; }
.suggestion-text { margin-top: 8px; color: #333; line-height: 1.6; }
.empty { padding: 20px; text-align: center; color: #999; }
</style>