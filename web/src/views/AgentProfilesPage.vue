<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AgentCard from '@/components/agents/AgentCard.vue'
import { useAgentStore } from '@/stores/agents'
import { sanitizeForLog } from '@/utils/logging'
import { useWebSocketSubscription } from '@/composables/useWebSocketSubscription'
import type { AgentConfig } from '@/api/types'

const router = useRouter()
const agentStore = useAgentStore()

useWebSocketSubscription({
  bindings: [{ channel: 'agents', handler: agentStore.handleWsEvent }],
})

onMounted(async () => {
  try {
    await agentStore.fetchAgents()
  } catch (err) {
    console.error('Initial data fetch failed:', sanitizeForLog(err))
  }
})

function openAgent(agent: AgentConfig) {
  router.push(`/agents/${encodeURIComponent(agent.name)}`)
}
</script>

<template>
  <AppShell>
    <PageHeader title="Agents" :subtitle="`${agentStore.total} agents in organization`" />

    <ErrorBoundary :error="agentStore.error" @retry="agentStore.fetchAgents()">
      <LoadingSkeleton v-if="agentStore.loading && agentStore.agents.length === 0" :lines="6" />
      <EmptyState
        v-else-if="agentStore.agents.length === 0"
        icon="pi pi-users"
        title="No agents"
        message="No agents are configured in this organization."
      />
      <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <AgentCard
          v-for="agent in agentStore.agents"
          :key="agent.name"
          :agent="agent"
          @click="openAgent"
        />
      </div>
    </ErrorBoundary>
  </AppShell>
</template>
