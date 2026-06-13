import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSceneStore = defineStore('scene', () => {
  const current = ref('gaokao')
  const scenes = [
    { id: 'gaokao', label: '高考志愿', icon: '🎓' },
    { id: 'kaoyan', label: '考研规划', icon: '📚' },
    { id: 'career', label: '职业方向', icon: '💼' },
  ]
  function switchScene(sceneId) { current.value = sceneId }
  return { current, scenes, switchScene }
})
