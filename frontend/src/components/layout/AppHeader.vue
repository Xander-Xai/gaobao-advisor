<template>
  <div class="header-bar">
    <div class="flex gap-1">
      <button
        v-for="s in enhancedScenes"
        :key="s.id"
        @click="handleSceneSwitch(s.id)"
        :class="['scene-tab', scene.current === s.id ? 'active' : 'inactive']"
      >
        <component :is="s.icon" class="w-4 h-4" />
        {{ s.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSceneStore } from '../../stores/scene'
import { useChatStore } from '../../stores/chat'
import { GraduationCap, BookOpen, Briefcase, MessageSquare } from '@lucide/vue'

const scene = useSceneStore()
const chat = useChatStore()

// Map scene IDs to Lucide icons
const iconMap = {
  gaokao: GraduationCap,
  kaoyan: BookOpen,
  career: Briefcase,
  general: MessageSquare,
}

// Enhance scene data with Lucide icon components
const enhancedScenes = computed(() =>
  scene.scenes.map(s => ({
    ...s,
    icon: iconMap[s.id] || null,
    iconName: s.id,
  }))
)

function handleSceneSwitch(sceneId) {
  if (scene.current === sceneId && chat.currentSessionId) return
  scene.switchScene(sceneId)
  chat.createSession(sceneId)
}
</script>

<style scoped>
.header-bar {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  gap: 8px;
}

.scene-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border-radius: var(--radius-full);
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  font-family: var(--font-body);
  transition: all var(--motion-fast) var(--ease-smooth);
}

.scene-tab.active {
  background: var(--red);
  color: white;
}

.scene-tab.inactive {
  background: transparent;
  color: var(--muted);
}

.scene-tab.inactive:hover {
  background: rgba(212, 49, 46, 0.06);
  color: var(--red);
}
</style>
