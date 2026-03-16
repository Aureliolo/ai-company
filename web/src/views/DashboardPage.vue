<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import ActiveTasksSummary from '@/components/dashboard/ActiveTasksSummary.vue'
import SpendingSummary from '@/components/dashboard/SpendingSummary.vue'
import RecentApprovals from '@/components/dashboard/RecentApprovals.vue'
import SystemStatus from '@/components/dashboard/SystemStatus.vue'
import { useAnalyticsStore } from '@/stores/analytics'
import { useTaskStore } from '@/stores/tasks'
import { useBudgetStore } from '@/stores/budget'
import { useApprovalStore } from '@/stores/approvals'
import { getHealth } from '@/api/endpoints/health'
import { formatCurrency, formatNumber } from '@/utils/format'
import { useToast } from 'primevue/usetoast'
import { sanitizeForLog } from '@/utils/logging'
import { useWebSocketSubscription } from '@/composables/useWebSocketSubscription'
import type { HealthStatus } from '@/api/types'

const analytics = useAnalyticsStore()
const taskStore = useTaskStore()
const budgetStore = useBudgetStore()
const approvalStore = useApprovalStore()
const toast = useToast()
const health = ref<HealthStatus | null>(null)
const loading = ref(true)

const { connected } = useWebSocketSubscription({
  bindings: [
    { channel: 'tasks', handler: taskStore.handleWsEvent },
    { channel: 'budget', handler: budgetStore.handleWsEvent },
    { channel: 'approvals', handler: approvalStore.handleWsEvent },
  ],
})

onMounted(async () => {
  // Fetch initial data
  try {
    const results = await Promise.allSettled([
      getHealth(),
      analytics.fetchMetrics(),
      taskStore.fetchTasks({ limit: 10 }),
      budgetStore.fetchConfig(),
      budgetStore.fetchRecords({ limit: 100 }),
      approvalStore.fetchApprovals({ limit: 10 }),
    ])
    if (results[0].status === 'fulfilled') {
      health.value = results[0].value
    }
    const labels = ['Health', 'Analytics', 'Tasks', 'Budget Config', 'Budget Records', 'Approvals']
    const failed = results
      .map((r, i) => r.status === 'rejected' ? labels[i] : null)
      .filter(Boolean)
    if (failed.length > 0) {
      results.forEach((r, i) => {
        if (r.status === 'rejected') {
          console.error(`Dashboard fetch failed [${labels[i]}]:`, sanitizeForLog(r.reason), r.reason)
        }
      })
      toast.add({
        severity: 'warn',
        summary: 'Dashboard partially loaded',
        detail: `Failed to load: ${failed.join(', ')}`,
        life: 5000,
      })
    }
  } finally {
    loading.value = false
  }
})

</script>

<template>
  <AppShell>
    <PageHeader title="Dashboard" subtitle="Overview of your synthetic organization" />

    <LoadingSkeleton v-if="loading" :lines="6" />

    <template v-else>
      <!-- Metric cards -->
      <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Tasks"
          :value="formatNumber(analytics.metrics?.total_tasks ?? 0)"
          icon="pi pi-check-square"
        />
        <MetricCard
          title="Active Agents"
          :value="formatNumber(analytics.metrics?.total_agents ?? 0)"
          icon="pi pi-users"
          color="bg-purple-600/10 text-purple-400"
        />
        <MetricCard
          title="Total Spending"
          :value="formatCurrency(analytics.metrics?.total_cost_usd ?? 0)"
          icon="pi pi-chart-bar"
          color="bg-green-600/10 text-green-400"
        />
        <MetricCard
          title="Pending Approvals"
          :value="formatNumber(approvalStore.pendingCount)"
          icon="pi pi-shield"
          color="bg-amber-600/10 text-amber-400"
        />
      </div>

      <!-- Main content grid -->
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div class="lg:col-span-2 space-y-6">
          <ActiveTasksSummary :tasks="taskStore.tasks" />
          <SpendingSummary
            :records="budgetStore.records"
            :total-cost="analytics.metrics?.total_cost_usd ?? 0"
          />
        </div>
        <div class="space-y-6">
          <SystemStatus :health="health" :ws-connected="connected" />
          <RecentApprovals :approvals="approvalStore.approvals" />
        </div>
      </div>
    </template>
  </AppShell>
</template>
