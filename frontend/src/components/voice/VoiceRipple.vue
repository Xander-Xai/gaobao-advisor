<template>
  <div class="absolute inset-0 flex items-center justify-center">
    <div v-if="active" class="absolute w-24 h-24 rounded-full bg-blue-400/20 animate-ping" />
    <div v-if="active" class="absolute w-20 h-20 rounded-full bg-blue-400/10 animate-pulse" />
  </div>
</template>

<script setup>
defineProps({ active: Boolean })
</script>
