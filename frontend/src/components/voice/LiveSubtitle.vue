<template>
  <div class="px-6 py-4 h-64 overflow-y-auto">
    <div v-if="userText" class="text-right mb-3">
      <span class="inline-block bg-blue-600/30 text-white/90 rounded-2xl rounded-br-sm px-4 py-2 text-sm">{{ userText }}</span>
    </div>
    <div v-if="assistantText" class="text-left">
      <span class="inline-block bg-white/10 text-white/90 rounded-2xl rounded-bl-sm px-4 py-2 text-sm">{{ assistantText }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  userText: String,
  assistantText: String,
  phase: String,
})
</script>
