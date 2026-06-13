<template>
  <div class="border-b border-gray-200 bg-white px-4 py-3 flex items-center gap-4">
    <div class="flex gap-2">
      <button v-for="s in scene.scenes" :key="s.id" @click="scene.switchScene(s.id)"
        :class="['px-3 py-1.5 rounded-full text-sm transition-colors', scene.current === s.id ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-500 hover:bg-gray-100']">
        {{ s.icon }} {{ s.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useSceneStore } from '../../stores/scene'
const scene = useSceneStore()
</script>
