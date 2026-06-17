<template>
  <div class="min-h-screen bg-gradient-to-br from-amber-50 to-orange-50">
    <AppHeader />

    <div class="max-w-3xl mx-auto px-6 py-8">
      <header class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-red-900">👤 用户画像</h1>
          <p class="text-sm text-gray-500 mt-1">session: {{ sessionId }}</p>
        </div>
        <div class="text-right">
          <div class="text-sm text-gray-500">完整度</div>
          <div class="flex items-center gap-2 mt-1">
            <div class="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-amber-400 to-red-600 transition-all"
                :style="{ width: completeness + '%' }"
              ></div>
            </div>
            <span class="text-sm font-medium text-red-900">{{ completeness }}%</span>
          </div>
        </div>
      </header>

      <!-- Auth gate -->
      <div
        v-if="!chatStore.sessionToken"
        class="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-sm text-amber-800"
      >
        ⚠ <strong>未认证</strong>：请先到
        <router-link to="/" class="underline text-blue-600">对话页</router-link>
        发送一条消息，后端会在 SSE done 事件中返回 session_token。
      </div>

      <!-- Error banner -->
      <div
        v-if="errorMessage"
        class="bg-red-50 border border-red-200 rounded-lg p-3 mb-6 text-sm text-red-700 flex justify-between items-center"
      >
        <span>❌ {{ errorMessage }}</span>
        <button @click="errorMessage = ''" class="text-red-500 hover:text-red-700">✕</button>
      </div>

      <!-- Next question card -->
      <div
        v-if="nextQuestion"
        class="bg-white rounded-xl shadow-sm border border-amber-200 p-5 mb-6"
      >
        <div class="text-xs uppercase tracking-wide text-amber-600 mb-1">灵魂提问 #{{ roundCount + 1 }}</div>
        <p class="text-gray-800 leading-relaxed">{{ nextQuestion }}</p>
      </div>

      <!-- Field grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="field in FIELDS"
          :key="field.key"
          class="bg-white rounded-xl shadow-sm border border-gray-100 p-4"
        >
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium text-gray-700">
              {{ field.label }}
              <span v-if="field.required" class="text-red-500">*</span>
            </label>
            <span
              v-if="isFilled(field.key)"
              class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700"
            >✓ 已填</span>
            <span
              v-else
              class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500"
            >未填</span>
          </div>

          <div v-if="!editing[field.key]">
            <div class="text-gray-800 text-sm min-h-[1.5em]">
              {{ displayValue(field.key) || '—' }}
            </div>
            <div class="flex gap-3 mt-2">
              <button
                @click="startEdit(field.key)"
                :disabled="!chatStore.sessionToken"
                class="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-300"
              >编辑</button>
              <button
                v-if="!field.required && !isFilled(field.key)"
                @click="skipField(field.key)"
                :disabled="!chatStore.sessionToken"
                class="text-xs text-gray-500 hover:text-gray-700 disabled:text-gray-300"
              >跳过</button>
            </div>
          </div>

          <div v-else class="flex gap-2 mt-2">
            <input
              v-model="editingValue"
              @keyup.enter="saveField(field.key)"
              @keyup.esc="cancelEdit()"
              :type="field.type || 'text'"
              :placeholder="field.placeholder"
              :min="field.min"
              :max="field.max"
              class="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              @click="saveField(field.key)"
              class="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >保存</button>
            <button
              @click="cancelEdit()"
              class="px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
            >取消</button>
          </div>
        </div>
      </div>

      <!-- Footer actions -->
      <div class="mt-8 flex justify-between">
        <router-link
          to="/"
          class="px-5 py-2.5 text-sm bg-white text-gray-700 rounded-lg border border-gray-300 hover:bg-gray-50"
        >← 返回对话</router-link>
        <button
          v-if="nextQuestion"
          @click="refreshNextQuestion"
          :disabled="!chatStore.sessionToken"
          class="px-5 py-2.5 text-sm bg-gradient-to-r from-amber-400 to-red-600 text-white rounded-lg shadow hover:opacity-90 disabled:opacity-40"
        >🔄 下一题</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { profileAPI } from '../api/client'
import AppHeader from '../components/layout/AppHeader.vue'

const route = useRoute()
const chatStore = useChatStore()

const sessionId = computed(() => route.params.sessionId || chatStore.currentSessionId)
const profile = ref({})
const isComplete = ref(false)
const missingFields = ref([])
const nextQuestion = ref(null)
const roundCount = ref(0)
const errorMessage = ref('')
const editing = reactive({})
const editingValue = ref('')

const FIELDS = [
  { key: 'province', label: '省份', required: true, placeholder: '山东' },
  { key: 'score', label: '分数', required: true, type: 'number', min: 100, max: 750, placeholder: '600' },
  { key: 'subject', label: '选科', required: true, placeholder: '物理 / 历史 / 物理+化学' },
  { key: 'interest', label: '意向专业', required: true, placeholder: '计算机 / 临床医学' },
  { key: 'region', label: '地域偏好', placeholder: '北京 / 江浙沪 / 不限' },
  { key: 'family', label: '家庭背景', placeholder: '工薪 / 公务员 / 自由职业' },
  { key: 'goal', label: '升学目标', placeholder: '就业 / 考研 / 出国 / 考公' },
]

const TOTAL_FIELDS = FIELDS.length
const completeness = computed(() => {
  const filled = FIELDS.filter(f => isFilled(f.key)).length
  return Math.round((filled / TOTAL_FIELDS) * 100)
})

function isFilled(key) {
  const v = profile.value?.[key]
  if (v === null || v === undefined) return false
  if (typeof v === 'string') return v.trim() !== ''
  return true
}

function displayValue(key) {
  const v = profile.value?.[key]
  if (key === 'score' && v) return `${v} 分`
  return v || ''
}

function startEdit(key) {
  editing[key] = true
  editingValue.value = String(profile.value?.[key] ?? '')
}

function cancelEdit() {
  for (const k of Object.keys(editing)) editing[k] = false
}

async function saveField(key) {
  if (!chatStore.sessionToken) {
    errorMessage.value = '请先发送一条消息获取 session token'
    return
  }
  const value = String(editingValue.value).trim()
  if (!value) {
    errorMessage.value = `${key} 不能为空`
    return
  }
  const { error } = await profileAPI.update(sessionId.value, { field: key, value }, chatStore.sessionToken)
  if (error) {
    errorMessage.value = `更新失败: ${error.message}`
    return
  }
  cancelEdit()
  await loadProfile()
  await loadNextQuestion()
}

async function skipField(key) {
  if (!chatStore.sessionToken) return
  const { error } = await profileAPI.skip(sessionId.value, { field: key }, chatStore.sessionToken)
  if (error) {
    errorMessage.value = `跳过失败: ${error.message}`
    return
  }
  await loadNextQuestion()
}

async function loadProfile() {
  if (!chatStore.sessionToken) return
  const { data, error } = await profileAPI.get(sessionId.value, chatStore.sessionToken)
  if (error) {
    errorMessage.value = `加载画像失败: ${error.message}`
    return
  }
  profile.value = data.profile || {}
  isComplete.value = data.is_complete
  missingFields.value = data.missing_fields || []
}

async function loadNextQuestion() {
  if (!chatStore.sessionToken) return
  const { data, error } = await profileAPI.nextQuestion(sessionId.value, chatStore.sessionToken)
  if (error) {
    errorMessage.value = `获取问题失败: ${error.message}`
    return
  }
  nextQuestion.value = data.question
  roundCount.value = data.round_count
}

async function refreshNextQuestion() {
  await loadNextQuestion()
}

onMounted(async () => {
  if (!sessionId.value) {
    errorMessage.value = '缺少 sessionId，请从对话页进入'
    return
  }
  if (chatStore.sessionToken) {
    await loadProfile()
    await loadNextQuestion()
  }
})
</script>
