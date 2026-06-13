import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'chat', component: () => import('../views/ChatView.vue') },
  { path: '/report/:id', name: 'report', component: () => import('../views/ReportView.vue') },
  { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
