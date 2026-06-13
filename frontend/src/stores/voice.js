import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVoiceStore = defineStore('voice', () => {
  const showModal = ref(false)
  function open() { showModal.value = true }
  function close() { showModal.value = false }
  return { showModal, open, close }
})
