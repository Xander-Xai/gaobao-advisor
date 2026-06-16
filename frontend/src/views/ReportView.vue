<template>
  <div class="report-page">
    <AppHeader />
    <div class="report-container">
      <div v-if="reportStore.loading" class="loading"><p>报告生成中...</p></div>
      <div v-else-if="reportStore.error" class="error">
        <p>❌ {{ reportStore.error }}</p>
        <button @click="loadReport">重试</button>
      </div>
      <div v-else-if="reportStore.hasReport" class="report-content">
        <ReportCover :reportId="reportId" />
        <section class="info-section">
          <h2>👤 考生信息</h2>
          <div class="info-grid">
            <div class="info-item"><span class="label">姓名</span><span class="value">{{ report.student_name || '未填写' }}</span></div>
            <div class="info-item"><span class="label">省份</span><span class="value">{{ report.province || '-' }}</span></div>
            <div class="info-item"><span class="label">分数</span><span class="value">{{ report.score ? report.score + '分' : '-' }}</span></div>
            <div class="info-item"><span class="label">选科</span><span class="value">{{ report.subject || '-' }}</span></div>
            <div class="info-item"><span class="label">意向专业</span><span class="value">{{ report.interest || '-' }}</span></div>
          </div>
        </section>
        <section class="summary-section"><div class="summary-box">{{ report.summary || '暂无摘要' }}</div></section>
        <section class="facts-section">
          <h2>📋 分析摘要</h2>
          <ul><li v-for="(fact, i) in report.facts" :key="i">{{ fact }}</li></ul>
        </section>
        <SchoolTable :suggestions="report.suggestions" />
        <section class="risks-section">
          <h2>⚠️ 风险提示</h2>
          <ul class="risk-list"><li v-for="(risk, i) in report.risks" :key="i">{{ risk }}</li></ul>
        </section>
        <section class="actions-section">
          <h2>📌 建议行动</h2>
          <ol><li v-for="(action, i) in report.next_actions" :key="i">{{ action }}</li></ol>
        </section>
        <ExportButton :reportId="reportId" />
      </div>
      <div v-else class="no-report">
        <p>暂无报告数据</p>
        <router-link to="/" class="back-link">返回对话页面</router-link>
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

async function loadReport() {
  if (reportId.value) await reportStore.fetchReport(reportId.value)
}

onMounted(loadReport)
</script>

<style scoped>
.report-page { min-height: 100vh; background: linear-gradient(135deg, #FFF8DC 0%, #FAEBD7 100%); }
.report-container { max-width: 900px; margin: 0 auto; padding: 20px; }
.loading, .error, .no-report { text-align: center; padding: 60px 20px; }
.error { color: #DC143C; }
.error button { margin-top: 16px; padding: 8px 24px; background: #8B0000; color: white; border: none; border-radius: 6px; cursor: pointer; }
.info-section, .facts-section, .risks-section, .actions-section { background: white; border-radius: 12px; padding: 24px; margin: 16px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.info-section h2, .facts-section h2, .risks-section h2, .actions-section h2 { color: #8B0000; font-size: 20px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #FFD700; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.info-item { display: flex; flex-direction: column; }
.info-item .label { font-size: 12px; color: #999; margin-bottom: 4px; }
.info-item .value { font-size: 16px; color: #333; font-weight: 500; }
.summary-section { margin: 16px 0; }
.summary-box { background: #FFF8DC; padding: 16px 20px; border-radius: 8px; color: #8B0000; font-size: 16px; line-height: 1.6; }
.facts-section ul, .risks-section ul, .actions-section ol { margin-left: 20px; }
.facts-section li, .actions-section li { margin-bottom: 8px; line-height: 1.6; color: #333; }
.risk-list li { color: #DC143C; }
.back-link { display: inline-block; margin-top: 16px; padding: 10px 24px; background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%); color: #8B0000; text-decoration: none; border-radius: 8px; font-weight: bold; }
</style>