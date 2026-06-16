import { createPinia, setActivePinia } from 'pinia'

// Create a fresh Pinia instance for each test
setActivePinia(createPinia())
