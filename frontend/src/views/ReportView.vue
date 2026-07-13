<template>
  <div class="report-page">
    <AppHeader />
    <div class="report-container">
      <!-- Loading -->
      <div v-if="reportStore.loading" class="report-state">
        <div class="loading-spinner">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--red)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
        </div>
        <p>报告生成中...</p>
      </div>

      <!-- Error -->
      <div v-else-if="reportStore.error" class="report-state">
        <p class="error-text">{{ reportStore.error }}</p>
        <button @click="loadReport" class="btn-retry">重试</button>
      </div>

      <!-- Report content -->
      <div v-else-if="reportStore.hasReport" class="report-content">
        <!-- 金榜 Hero -->
        <div class="report-hero">
          <h1>{{ coverTitle }}</h1>
          <p class="hero-subtitle">{{ reportTitle }} · {{ new Date().getFullYear() }}</p>
          <div class="hero-line"></div>
          <p v-if="report.confidence" class="hero-confidence">可信度 {{ Math.round(report.confidence * 100) }}%</p>
        </div>

        <!-- Student Info -->
        <section class="report-section">
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><path d="M16 8.2C16 7 15 6 13.8 6h-.4C12 6 11 7 11 8.2v2.3h5v-2.3Z"/></svg>
            考生信息
          </h2>
          <div class="info-grid">
            <div class="info-item"><span class="info-label">姓名</span><span class="info-value">{{ report.student_name || '未填写' }}</span></div>
            <div class="info-item"><span class="info-label">省份</span><span class="info-value">{{ report.province || '-' }}</span></div>
            <div class="info-item"><span class="info-label">分数</span><span class="info-value">{{ report.score ? report.score + '分' : '-' }}</span></div>
            <div class="info-item"><span class="info-label">选科</span><span class="info-value">{{ report.subject || '-' }}</span></div>
            <div class="info-item"><span class="info-label">意向</span><span class="info-value">{{ report.interest || '-' }}</span></div>
          </div>
        </section>

        <!-- Summary -->
        <section class="report-section">
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
            综合分析
          </h2>
          <div class="summary-box">{{ report.summary || '暂无摘要' }}</div>
        </section>

        <!-- Facts -->
        <section class="report-section">
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
            数据分析
          </h2>
          <ul class="fact-list">
            <li v-for="(fact, i) in report.facts" :key="i" class="fact-item">{{ fact }}</li>
          </ul>
        </section>

        <!-- School Suggestions -->
        <SchoolTable :suggestions="report.suggestions" />

        <!-- Risks -->
        <section class="report-section">
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            风险提示
          </h2>
          <ul class="risk-list">
            <li v-for="(risk, i) in report.risks" :key="i" class="risk-item">{{ risk }}</li>
          </ul>
        </section>

        <!-- Actions -->
        <section class="report-section">
          <h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="section-icon"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            建议行动
          </h2>
          <ol class="action-list">
            <li v-for="(action, i) in report.next_actions" :key="i" class="action-item">{{ action }}</li>
          </ol>
        </section>

        <ExportButton :reportId="reportId" />
      </div>

      <!-- No report -->
      <div v-else class="report-state">
        <p>暂无报告数据</p>
        <router-link to="/" class="link-back">返回对话页面</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useReportStore } from '../stores/report'
import AppHeader from '../components/layout/AppHeader.vue'
import ReportCover from '../components/report/ReportCover.vue'
import SchoolTable from '../components/report/SchoolTable.vue'
import ExportButton from '../components/report/ExportButton.vue'

const route = useRoute()
const reportStore = useReportStore()
const reportId = computed(() => route.params.id)
const report = computed(() => reportStore.report)

const reportTitle = computed(() => {
  const scene = report.value?.scene
  const titles = {
    gaokao: '高考志愿填报分析报告',
    kaoyan: '考研规划分析报告',
    career: '职业方向分析报告',
  }
  return titles[scene] || '综合分析报告'
})

const coverTitle = computed(() => {
  const scene = report.value?.scene
  const titles = {
    gaokao: '金 榜 题 名',
    kaoyan: '志 在 必 得',
    career: '前 程 似 锦',
  }
  return titles[scene] || '明 辨 笃 行'
})

async function loadReport() {
  if (reportId.value) await reportStore.fetchReport(reportId.value)
}

onMounted(loadReport)
</script>

<style scoped>
.report-page {
  min-height: 100vh;
  background: var(--paper);
}

.report-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px 24px;
}

/* Loading / Error / Empty state */
.report-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}

.report-state p {
  margin-top: 12px;
  font-size: 15px;
}

.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-text {
  color: var(--red);
  margin-bottom: 16px;
}

.btn-retry {
  padding: 10px 24px;
  background: var(--red);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font: 600 14px var(--font-body);
}

.link-back {
  display: inline-block;
  margin-top: 16px;
  padding: 10px 24px;
  background: linear-gradient(135deg, var(--gold) 0%, var(--red) 100%);
  color: white;
  text-decoration: none;
  border-radius: var(--radius-md);
  font-weight: 600;
}

/* 金榜 Hero */
.report-hero {
  background: linear-gradient(135deg, var(--gold) 0%, #D4A843 30%, var(--gold) 60%, var(--gold-dark) 100%);
  border-radius: var(--radius-xl);
  padding: 48px 32px 40px;
  text-align: center;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}

.report-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(255,215,0,0.15) 0%, transparent 70%),
    radial-gradient(ellipse at 80% 50%, rgba(255,215,0,0.10) 0%, transparent 70%);
}

.report-hero h1 {
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 700;
  color: white;
  letter-spacing: 0.15em;
  text-shadow: 0 2px 8px rgba(0,0,0,0.15);
  position: relative;
}

.hero-subtitle {
  font-size: 14px;
  color: rgba(255,255,255,0.85);
  margin-top: 8px;
  letter-spacing: 0.04em;
  position: relative;
}

.hero-line {
  width: 60px;
  height: 2px;
  background: rgba(255,255,255,0.4);
  margin: 12px auto 0;
  position: relative;
}

.hero-confidence {
  font-size: 12px;
  color: rgba(255,255,255,0.7);
  margin-top: 8px;
  position: relative;
}

/* Report sections */
.report-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
}

.report-section h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  padding-bottom: 10px;
  border-bottom: 2px solid var(--gold);
  margin-bottom: 16px;
}

.section-icon {
  color: var(--gold);
  flex-shrink: 0;
}

/* Student info grid */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 11px;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

/* Summary */
.summary-box {
  background: var(--gold-light);
  border: 1px solid var(--gold);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  color: var(--gold-dark);
  font-size: 15px;
  line-height: 1.7;
}

/* Facts */
.fact-list {
  list-style: none;
  padding: 0;
}

.fact-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  line-height: 1.6;
  color: var(--secondary);
}

.fact-item:last-child {
  border-bottom: none;
}

/* Risks */
.risk-list {
  list-style: none;
  padding: 0;
}

.risk-item {
  position: relative;
  padding: 10px 0 10px 20px;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  line-height: 1.6;
  color: var(--secondary);
}

.risk-item::before {
  content: '⚠';
  position: absolute;
  left: 0;
  color: var(--red);
}

.risk-item:last-child {
  border-bottom: none;
}

/* Actions */
.action-list {
  list-style: none;
  counter-reset: action-counter;
  padding: 0;
}

.action-item {
  position: relative;
  padding: 10px 0 10px 36px;
  border-bottom: 1px solid var(--border-light);
  font-size: 14px;
  line-height: 1.6;
  color: var(--secondary);
  counter-increment: action-counter;
}

.action-item::before {
  content: counter(action-counter);
  position: absolute;
  left: 0;
  top: 10px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--red);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.action-item:last-child {
  border-bottom: none;
}
</style>