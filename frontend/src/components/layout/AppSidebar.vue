<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <span class="brand-icon">顾</span>
        <span>志愿顾问</span>
      </div>
      <button @click="chat.createSession(scene.current)" class="btn-new-chat">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        新对话
      </button>
    </div>
    <div class="sidebar-list">
      <div
        v-for="s in chat.sessions"
        :key="s.id"
        @click="chat.switchSession(s.id)"
        :class="['conv-item', s.id === chat.currentSessionId ? 'active' : '']"
      >
        {{ s.title || '新对话' }}
      </div>
      <p v-if="!chat.sessions.length" class="sidebar-empty">点击上方按钮开始</p>
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from '../../stores/chat'
import { useSceneStore } from '../../stores/scene'
const chat = useChatStore()
const scene = useSceneStore()
</script>

<style scoped>
.sidebar {
  width: 260px;
  background: var(--sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--red);
}

.brand-icon {
  width: 28px;
  height: 28px;
  background: var(--red);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 13px;
  font-family: var(--font-display);
  font-weight: 700;
}

.btn-new-chat {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: var(--red);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-body);
  transition: background var(--motion-fast) var(--ease-smooth);
}

.btn-new-chat:hover {
  background: var(--red-dark);
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 14px;
  color: var(--secondary);
  transition: all var(--motion-fast) var(--ease-smooth);
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-item:hover {
  background: rgba(0, 0, 0, 0.04);
  color: var(--ink);
}

.conv-item.active {
  background: var(--red-light);
  color: var(--red);
  font-weight: 600;
}

.sidebar-empty {
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  margin-top: 32px;
}
</style>