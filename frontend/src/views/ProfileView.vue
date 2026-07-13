<template>
  <div class="profile-page">
    <AppHeader />

    <div class="profile-container">
      <!-- Header -->
      <header class="profile-header">
        <div class="header-left">
          <h1 class="page-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            用户画像
          </h1>
          <p class="session-label">session: {{ sessionId }}</p>
        </div>
        <div class="completeness-box">
          <div class="comp-label">完整度</div>
          <div class="comp-bar">
            <div class="comp-fill" :style="{ width: completeness + '%' }"></div>
          </div>
          <span class="comp-pct"><span class="comp-num">{{ completeness }}</span>%</span>
        </div>
      </header>

      <!-- Auth gate -->
      <div v-if="!chatStore.sessionToken" class="msg-warning">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <span><strong>未认证：</strong>请先到 <router-link to="/" class="link-inline">对话页</router-link> 发送一条消息获取 session token。</span>
      </div>

      <!-- Error -->
      <div v-if="errorMessage" class="msg-error">
        <span>{{ errorMessage }}</span>
        <button @click="errorMessage = ''" class="error-dismiss">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <!-- Soul question -->
      <div v-if="nextQuestion" class="soul-card">
        <div class="soul-tag">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          灵魂提问 #{{ roundCount + 1 }}
        </div>
        <p class="soul-text">{{ nextQuestion }}</p>
      </div>

      <!-- Field grid -->
      <div class="field-grid">
        <div
          v-for="field in FIELDS"
          :key="field.key"
          class="field-card"
        >
          <div class="field-top">
            <span class="field-label-text">
              {{ field.label }}
              <span v-if="field.required" class="required-star">*</span>
            </span>
            <span
              v-if="isFilled(field.key)"
              class="badge badge-filled"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              已填
            </span>
            <span v-else class="badge badge-empty">未填</span>
          </div>

          <!-- Display mode -->
          <div v-if="!editing[field.key]">
            <div :class="['field-value', isFilled(field.key) ? 'filled' : 'empty']">
              {{ displayValue(field.key) || '—' }}
            </div>
            <div class="field-actions">
              <button
                @click="startEdit(field.key)"
                :disabled="!chatStore.sessionToken"
                class="action-btn action-edit"
              >编辑</button>
              <button
                v-if="!field.required && !isFilled(field.key)"
                @click="skipField(field.key)"
                :disabled="!chatStore.sessionToken"
                class="action-btn action-skip"
              >跳过</button>
            </div>
          </div>

          <!-- Edit mode -->
          <div v-else class="edit-row">
            <input
              v-model="editingValue"
              @keyup.enter="saveField(field.key)"
              @keyup.esc="cancelEdit()"
              :type="field.type || 'text'"
              :placeholder="field.placeholder"
              :min="field.min"
              :max="field.max"
              class="edit-input"
            />
            <button @click="saveField(field.key)" class="save-btn">保存</button>
            <button @click="cancelEdit()" class="cancel-btn">取消</button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="profile-footer">
        <router-link to="/" class="btn-back">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          返回对话
        </router-link>
        <button
          v-if="nextQuestion"
          @click="refreshNextQuestion"
          :disabled="!chatStore.sessionToken"
          class="btn-next"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          下一题
        </button>
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

<style scoped>
.profile-page {
  min-height: 100vh;
  background: var(--paper);
}

.profile-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* Header */
.profile-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
}

.session-label {
  font-size: 13px;
  color: var(--muted);
}

.completeness-box {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.comp-label {
  font-size: 12px;
  color: var(--muted);
}

.comp-bar {
  width: 140px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}

.comp-fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--gold) 0%, var(--red) 100%);
  transition: width 0.4s ease;
}

.comp-pct {
  font-size: 14px;
  font-weight: 600;
  color: var(--secondary);
}

.comp-num {
  color: var(--red);
}

/* Messages */
.msg-warning {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  background: var(--gold-light);
  border: 1px solid var(--gold);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--gold-dark);
  line-height: 1.5;
}

.link-inline {
  color: var(--red);
  text-decoration: underline;
}

.msg-error {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--red-light);
  border: 1px solid var(--red);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: 20px;
  font-size: 13px;
  color: var(--red);
  line-height: 1.5;
}

.error-dismiss {
  background: none;
  border: none;
  color: var(--red);
  cursor: pointer;
  font-size: 18px;
  padding: 0 4px;
}

/* Soul question */
.soul-card {
  background: var(--surface);
  border: 1px solid var(--gold);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(198, 146, 42, 0.08);
}

.soul-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--gold-dark);
  margin-bottom: 8px;
}

.soul-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--ink);
}

/* Field grid */
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 24px;
}

.field-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px;
  transition: box-shadow var(--motion-fast) var(--ease-smooth);
}

.field-card:hover {
  box-shadow: var(--shadow-raised);
}

.field-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.field-label-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--secondary);
}

.required-star {
  color: var(--red);
  margin-left: 2px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 500;
}

.badge-filled {
  background: var(--success-light);
  color: var(--success);
}

.badge-empty {
  background: var(--border);
  color: var(--muted);
}

.field-value {
  font-size: 14px;
  min-height: 1.5em;
  margin-bottom: 8px;
}

.field-value.filled {
  color: var(--ink);
  font-weight: 500;
}

.field-value.empty {
  color: var(--disabled);
}

.field-actions {
  display: flex;
  gap: 12px;
}

.action-btn {
  font-size: 12px;
  border: none;
  background: none;
  cursor: pointer;
  padding: 2px 0;
  font-family: var(--font-body);
  transition: color var(--motion-fast);
}

.action-edit {
  color: var(--red);
}

.action-edit:hover {
  color: var(--red-dark);
}

.action-skip {
  color: var(--muted);
}

.action-skip:hover {
  color: var(--secondary);
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Edit mode */
.edit-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.edit-input {
  flex: 1;
  background: var(--elevated);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  font: 400 14px var(--font-body);
  color: var(--ink);
  outline: none;
}

.edit-input:focus {
  border-color: var(--red);
  box-shadow: 0 0 0 3px rgba(212, 49, 46, 0.12);
}

.save-btn {
  padding: 8px 14px;
  background: var(--red);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font: 600 13px var(--font-body);
  cursor: pointer;
}

.save-btn:hover {
  background: var(--red-dark);
}

.cancel-btn {
  padding: 8px 14px;
  background: transparent;
  color: var(--secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font: 500 13px var(--font-body);
  cursor: pointer;
}

.cancel-btn:hover {
  border-color: var(--muted);
  color: var(--ink);
}

/* Footer */
.profile-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.btn-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: var(--surface);
  color: var(--secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font: 500 14px var(--font-body);
  text-decoration: none;
  cursor: pointer;
  transition: all var(--motion-fast) var(--ease-smooth);
}

.btn-back:hover {
  border-color: var(--muted);
  color: var(--ink);
}

.btn-next {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  background: linear-gradient(135deg, var(--gold) 0%, var(--red) 100%);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font: 600 14px var(--font-body);
  cursor: pointer;
  transition: opacity var(--motion-fast);
}

.btn-next:hover {
  opacity: 0.9;
}

.btn-next:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 768px) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .profile-header {
    flex-direction: column;
    gap: 12px;
  }

  .completeness-box {
    align-items: flex-start;
  }
}
</style>