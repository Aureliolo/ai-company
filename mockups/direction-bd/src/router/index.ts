import { createRouter, createWebHashHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import OrgView from '../views/OrgView.vue'
import AgentView from '../views/AgentView.vue'

const router = createRouter({
  history: createWebHashHistory('/bd/'),
  routes: [
    { path: '/', component: DashboardView },
    { path: '/org', component: OrgView },
    { path: '/agent', component: AgentView },
  ],
})

export default router
