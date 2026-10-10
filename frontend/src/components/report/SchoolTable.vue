<template>
  <section class="report-section">
    <h2>
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      院校推荐
    </h2>
    <div v-if="grouped.length" class="school-categories">
      <div v-for="group in grouped" :key="group.level" class="school-category">
        <div class="category-header">
          <span :class="['category-badge', group.level]">{{ group.label }}</span>
          <span class="category-desc">{{ group.desc }}</span>
        </div>
        <div class="school-cards">
          <div
            v-for="(item, i) in group.items"
            :key="i"
            :class="['school-card', group.level]"
          >
            <div class="school-name">{{ item.name || item.text }}</div>
            <div v-if="item.probability" :class="['school-prob', probClass(item.probability)]">{{ item.probability }}%</div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <p>暂无推荐数据，建议继续对话获取详细分析</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ suggestions: { type: Array, default: () => [] } })

const grouped = computed(() => {
  const groups = { rush: [], stable: [], safe: [] }
  // If suggestions are simple strings, try to categorize by content
  for (const s of props.suggestions) {
    const text = typeof s === 'string' ? s : s.text || ''
    const name = typeof s === 'object' ? s.name : ''
    const probability = typeof s === 'object' ? s.probability : null
    const item = { text, name: name || text, probability }

    if (text.includes('冲')) groups.rush.push(item)
    else if (text.includes('稳')) groups.stable.push(item)
    else if (text.includes('保')) groups.safe.push(item)
    else groups.stable.push(item) // default to stable
  }

  const result = []
  if (groups.rush.length) result.push({ level: 'rush', label: '冲', desc: '希望较小，值得尝试', items: groups.rush })
  if (groups.stable.length) result.push({ level: 'stable', label: '稳', desc: '希望较大，主要填报目标', items: groups.stable })
  if (groups.safe.length) result.push({ level: 'safe', label: '保', desc: '非常稳妥，确保有保底', items: groups.safe })
  return result
})

const descMap = { rush: '希望较小，值得尝试', stable: '希望较大，主要填报目标', safe: '非常稳妥，确保有保底' }

function probClass(p) {
  if (p >= 80) return 'prob-high'
  if (p >= 55) return 'prob-mid'
  return 'prob-low'
}
</script>

<style scoped>
.report-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
}

.report-section h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--gold);
  margin-bottom: 16px;
}

.section-icon {
  color: var(--gold);
  flex-shrink: 0;
}

.school-categories {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.category-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.category-badge.rush {
  background: var(--red-light);
  color: var(--red);
}

.category-badge.stable {
  background: var(--gold-light);
  color: var(--gold-dark);
}

.category-badge.safe {
  background: var(--success-light);
  color: var(--success);
}

.category-desc {
  font-size: 13px;
  color: var(--muted);
}

.school-cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.school-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--elevated);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  transition: box-shadow var(--motion-fast);
}

.school-card:hover {
  box-shadow: var(--shadow-raised);
}

.school-card.rush { border-left: 3px solid var(--red); }
.school-card.stable { border-left: 3px solid var(--gold); }
.school-card.safe { border-left: 3px solid var(--success); }

.school-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}

.school-prob {
  font-size: 14px;
  font-weight: 700;
}

.prob-high { color: var(--success); }
.prob-mid { color: var(--gold-dark); }
.prob-low { color: var(--red); }

.empty-state {
  padding: 20px;
  text-align: center;
  color: var(--muted);
  font-size: 14px;
}
</style>