<template>
  <div class="ripple-wrapper">
    <div v-if="active" class="ripple-ring"></div>
    <div v-if="active" class="ripple-ring" style="animation-delay: 0.6s;"></div>
    <div v-if="active" class="ripple-ring" style="animation-delay: 1.2s;"></div>
  </div>
</template>

<script setup>
defineProps({ active: Boolean })
</script>

<style scoped>
.ripple-wrapper {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ripple-ring {
  position: absolute;
  width: 120px;
  height: 120px;
  border: 2px solid var(--red);
  border-radius: 50%;
  opacity: 0;
  animation: ripple-expand 2s ease-out infinite;
}

@keyframes ripple-expand {
  0%   { transform: scale(0.8); opacity: 0.3; }
  100% { transform: scale(1.6); opacity: 0; }
}
</style>