<template>
  <div class="bg-gray-900 text-white flex flex-col h-full">
    <div class="p-4">
      <button @click="chat.createSession(scene.current)" class="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium hover:bg-blue-700 transition-colors">
        + 新对话
      </button>
    </div>
    <div class="flex-1 overflow-y-auto px-2">
      <div v-for="s in chat.sessions" :key="s.id"
        @click="chat.selectSession(s.id)"
        :class="['rounded-lg px-3 py-2.5 mb-1 cursor-pointer text-sm truncate', s.id === chat.currentSessionId ? 'bg-gray-700' : 'hover:bg-gray-800']">
        {{ s.title || '新对话' }}
      </div>
      <p v-if="!chat.sessions.length" class="text-gray-500 text-xs text-center mt-8">点击上方按钮开始</p>
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from '../../stores/chat'
import { useSceneStore } from '../../stores/scene'
const chat = useChatStore()
const scene = useSceneStore()
</script>
