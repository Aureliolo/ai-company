import { createRouter, createWebHistory } from 'vue-router'
import { defineComponent, h } from 'vue'
import { authGuard } from './guards'

// Minimal placeholder — page views added in feat/web-dashboard-pages
const PlaceholderHome = defineComponent({
  name: 'PlaceholderHome',
  render() {
    return h('div', { class: 'flex items-center justify-center h-full text-slate-400' }, 'Dashboard loading…')
  },
})

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginPage.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('@/views/SetupPage.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      name: 'home',
      component: PlaceholderHome,
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach(authGuard)

export { router }
