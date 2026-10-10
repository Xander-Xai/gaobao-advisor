import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSceneStore = defineStore('scene', () => {
  const current = ref('gaokao')
  const scenes = [
    { id: 'gaokao', label: '高考志愿' },
    { id: 'kaoyan', label: '考研规划' },
    { id: 'career', label: '职业方向' },
    { id: 'general', label: '通用咨询' },
  ]
  function switchScene(sceneId) { current.value = sceneId }
  return { current, scenes, switchScene }
})
