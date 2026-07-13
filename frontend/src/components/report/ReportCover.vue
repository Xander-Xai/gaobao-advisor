<template>
  <div class="cover-wrapper">
    <img v-if="coverUrl" :src="coverUrl" alt="金榜题名封面" class="cover-img" />
    <div v-else class="cover-placeholder"><p>封面加载中...</p></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useReportStore } from '../../stores/report'
const props = defineProps({ reportId: { type: String, required: true } })
const reportStore = useReportStore()
const coverUrl = computed(() => reportStore.coverURL(props.reportId))
</script>

<style scoped>
.cover-wrapper {
  display: flex;
  justify-content: center;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  margin-bottom: 16px;
}

.cover-img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-modal);
}

.cover-placeholder {
  width: 800px;
  height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
  border-radius: var(--radius-md);
  color: white;
  font-size: 20px;
  font-family: var(--font-display);
}
</style>
