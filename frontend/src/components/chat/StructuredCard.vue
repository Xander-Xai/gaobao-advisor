<template>
  <section
    data-testid="structured-card"
    class="mt-3 rounded-xl border border-blue-100 bg-blue-50/60 p-3 text-gray-800"
    aria-label="结构化规划建议"
  >
    <header class="flex items-start justify-between gap-3">
      <div>
        <h4 class="text-sm font-semibold text-blue-950">{{ card.title || '规划建议' }}</h4>
        <p v-if="card.summary" class="mt-1 text-xs leading-relaxed text-gray-600">{{ card.summary }}</p>
      </div>
      <span
        v-if="confidencePercent !== null"
        data-testid="structured-confidence"
        class="shrink-0 rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-blue-700 border border-blue-100"
      >完整度 {{ confidencePercent }}%</span>
    </header>

    <dl class="mt-3 space-y-2.5">
      <div v-if="hasItems(card.facts)" data-testid="structured-facts">
        <dt class="text-[11px] font-semibold uppercase tracking-wide text-blue-700">已掌握信息</dt>
        <dd class="mt-1">
          <ul class="list-disc space-y-0.5 pl-4 text-xs leading-relaxed">
            <li v-for="(item, index) in card.facts" :key="`fact-${index}`">{{ item }}</li>
          </ul>
        </dd>
      </div>

      <div v-if="hasItems(card.suggestions)" data-testid="structured-suggestions">
        <dt class="text-[11px] font-semibold uppercase tracking-wide text-blue-700">推荐与依据</dt>
        <dd class="mt-1">
          <ul class="list-disc space-y-0.5 pl-4 text-xs leading-relaxed">
            <li v-for="(item, index) in card.suggestions" :key="`suggestion-${index}`">{{ item }}</li>
          </ul>
        </dd>
      </div>

      <div v-if="hasItems(card.risks)" data-testid="structured-risks">
        <dt class="text-[11px] font-semibold uppercase tracking-wide text-amber-700">风险提示</dt>
        <dd class="mt-1">
          <ul class="list-disc space-y-0.5 pl-4 text-xs leading-relaxed text-amber-900">
            <li v-for="(item, index) in card.risks" :key="`risk-${index}`">{{ item }}</li>
          </ul>
        </dd>
      </div>

      <div v-if="hasItems(card.next_actions)" data-testid="structured-next-actions">
        <dt class="text-[11px] font-semibold uppercase tracking-wide text-gray-600">下一步</dt>
        <dd class="mt-1">
          <ul class="list-disc space-y-0.5 pl-4 text-xs leading-relaxed">
            <li v-for="(item, index) in card.next_actions" :key="`action-${index}`">{{ item }}</li>
          </ul>
        </dd>
      </div>

      <div v-if="hasItems(card.sources)" data-testid="structured-sources">
        <dt class="text-[11px] font-semibold uppercase tracking-wide text-gray-500">来源与依据</dt>
        <dd class="mt-1">
          <ul class="list-disc space-y-0.5 pl-4 text-[11px] leading-relaxed text-gray-500">
            <li v-for="(item, index) in card.sources" :key="`source-${index}`" class="break-words">{{ item }}</li>
          </ul>
        </dd>
      </div>
    </dl>

    <p class="mt-3 border-t border-blue-100 pt-2 text-[11px] leading-relaxed text-gray-500">
      本卡片由对话与结构化查询生成；演示环境默认使用 SYNTHETIC_DEMO 合成数据，
      不构成真实志愿填报建议，请以各省教育考试院官方信息为准。
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  card: {
    type: Object,
    required: true,
  },
})

function hasItems(value) {
  return Array.isArray(value) && value.length > 0
}

const confidencePercent = computed(() => {
  const value = Number(props.card?.confidence)
  if (!Number.isFinite(value) || value < 0) return null
  return Math.round(Math.min(1, value) * 100)
})
</script>
