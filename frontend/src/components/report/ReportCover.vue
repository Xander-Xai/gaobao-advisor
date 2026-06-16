<template>
  <div class="cover-container">
    <img v-if="coverUrl" :src="coverUrl" alt="金榜题名封面" class="cover-image" />
    <div v-else class="cover-placeholder"><p>封面加载中...</p></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ reportId: { type: String, required: true } })
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const coverUrl = computed(() => `${API_BASE}/report/${props.reportId}/cover.svg`)
</script>

<style scoped>
.cover-container { display: flex; justify-content: center; padding: 20px; background: linear-gradient(135deg, #FFF8DC 0%, #FAEBD7 100%); }
.cover-image { max-width: 100%; height: auto; border-radius: 12px; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15); }
.cover-placeholder { width: 800px; height: 500px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); border-radius: 12px; color: #8B0000; font-size: 24px; }
</style>