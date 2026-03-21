<script setup lang="ts">
import { computed, nextTick, onMounted, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { VueFlow, useVueFlow, type Node, type Edge } from '@vue-flow/core'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import AppShell from '@/components/layout/AppShell.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ErrorBoundary from '@/components/common/ErrorBoundary.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import OrgNode from '@/components/org-chart/OrgNode.vue'
import { useCompanyStore } from '@/stores/company'
import { useAgentStore } from '@/stores/agents'
import { formatLabel } from '@/utils/format'

const router = useRouter()
const companyStore = useCompanyStore()
const agentStore = useAgentStore()
const { fitView } = useVueFlow()

async function retryFetch() {
  await Promise.all([companyStore.fetchDepartments(), agentStore.fetchAgents()])
}

onMounted(retryFetch)

const isLoading = computed(
  () => companyStore.departmentsLoading || agentStore.loading,
)

const hasDepartments = computed(
  () => companyStore.departments.length > 0,
)

const combinedError = computed(() => {
  const errors = [companyStore.departmentsError, agentStore.error].filter(Boolean)
  return errors.length > 0 ? errors.join(' | ') : null
})

const nodes = computed<Node[]>(() => {
  const result: Node[] = []
  let y = 0

  const agentIndex = new Map(agentStore.agents.map((a) => [a.name, a]))
  const addedAgents = new Set<string>()

  for (const dept of companyStore.departments) {
    const deptId = `dept-${dept.name}`
    result.push({
      id: deptId,
      position: { x: 0, y },
      data: { label: formatLabel(dept.name), type: 'department' },
      type: 'orgNode',
    })
    y += 120

    for (const team of dept.teams) {
      const teamId = `team-${dept.name}-${team.name}`
      result.push({
        id: teamId,
        position: { x: 50, y },
        data: { label: team.name, type: 'team' },
        type: 'orgNode',
      })
      y += 100
      for (let i = 0; i < team.members.length; i++) {
        const memberName = team.members[i]
        if (addedAgents.has(memberName)) continue
        addedAgents.add(memberName)
        const agent = agentIndex.get(memberName)
        result.push({
          id: `agent-${memberName}`,
          position: { x: 100 + i * 200, y },
          data: {
            label: memberName,
            type: 'agent',
            status: agent?.status,
            role: agent?.role,
            level: agent?.level,
          },
          type: 'orgNode',
        })
      }
      y += 120
    }
  }

  return result
})

const edges = computed<Edge[]>(() => {
  const result: Edge[] = []

  for (const dept of companyStore.departments) {
    const deptId = `dept-${dept.name}`
    for (const team of dept.teams) {
      const teamId = `team-${dept.name}-${team.name}`
      result.push({
        id: `${deptId}-${teamId}`,
        source: deptId,
        target: teamId,
        animated: true,
      })
      for (const member of team.members) {
        result.push({
          id: `${teamId}-agent-${member}`,
          source: teamId,
          target: `agent-${member}`,
        })
      }
    }
  }

  return result
})

watch(
  () => nodes.value.length,
  async (len) => {
    if (len > 0) {
      await nextTick()
      try {
        await fitView()
      } catch {
        // fitView may throw if viewport is not ready; fit-view-on-init handles initial render
      }
    }
  },
  { once: true },
)

function onNodeClick(event: { node: Node }) {
  if (event.node.id.startsWith('agent-')) {
    const name = event.node.id.slice('agent-'.length)
    router.push(`/agents/${encodeURIComponent(name)}`)
  } else if (
    event.node.id.startsWith('dept-') ||
    event.node.id.startsWith('team-')
  ) {
    router.push('/agents')
  }
}
</script>

<template>
  <AppShell>
    <PageHeader title="Organization Chart" subtitle="Visual structure of departments, teams, and agents" />

    <ErrorBoundary :error="combinedError" @retry="retryFetch">
      <LoadingSkeleton v-if="isLoading && !hasDepartments" :lines="6" />
      <EmptyState
        v-else-if="!hasDepartments"
        icon="pi pi-sitemap"
        title="No departments"
        message="Your organization has no departments configured yet. Set up your company structure to see the org chart."
      >
        <template #action>
          <RouterLink
            to="/settings"
            class="text-sm text-brand-400 hover:text-brand-300"
          >
            Go to Settings
          </RouterLink>
        </template>
      </EmptyState>
      <div v-else class="h-[calc(100vh-200px)] rounded-lg border border-slate-800 bg-slate-900">
        <VueFlow
          :nodes="nodes"
          :edges="edges"
          fit-view-on-init
          @node-click="onNodeClick"
        >
          <template #node-orgNode="{ data }">
            <OrgNode :data="data" />
          </template>
          <Controls />
          <MiniMap />
        </VueFlow>
      </div>
    </ErrorBoundary>
  </AppShell>
</template>
