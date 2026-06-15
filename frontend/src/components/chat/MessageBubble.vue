<template>
  <div :class="['flex', message.role === 'user' ? 'justify-end' : 'justify-start']">
    <div :class="['max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
      message.role === 'user' ? 'bg-blue-600 text-white rounded-br-sm' : 'bg-white text-gray-800 shadow-sm border border-gray-100 rounded-bl-sm']">
      <div v-html="renderedContent" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../../utils/sanitize'
const props = defineProps({ message: Object })
const renderedContent = computed(() => {
  return renderMarkdown(props.message.content || '')
})
</script>
