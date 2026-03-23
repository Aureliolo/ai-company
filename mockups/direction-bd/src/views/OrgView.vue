<template>
  <div class="org-layout">
    <TopBar />
    <div class="org-body">
      <Sidebar />
      <div class="org-main">
        <!-- Toolbar -->
        <div class="org-toolbar">
          <button v-if="zoomedDept" class="back-btn" @click="zoomOut">
            ← Back to all departments
          </button>
          <div v-if="zoomedDept" class="dept-banner" :style="{ '--dept-col': deptColors[zoomedDept] }">
            <span class="dept-name">{{ zoomedDept }}</span>
            <span class="dept-stats mono">{{ deptStats[zoomedDept]?.agents }} agents · {{ deptStats[zoomedDept]?.active }} active · ${{ deptStats[zoomedDept]?.spent }} today</span>
          </div>
          <div v-else class="view-hint">Click a department cluster to zoom in</div>
        </div>

        <!-- Department overlay cards (when zoomed out) -->
        <div v-if="!zoomedDept" class="dept-overlay">
          <div
            v-for="(stats, dept) in deptStats"
            :key="dept"
            class="dept-card"
            :style="{ '--dept-col': deptColors[dept] }"
            @click="zoomIntoDept(dept)"
          >
            <div class="dept-card-name">{{ dept }}</div>
            <div class="dept-card-row">
              <span class="mono">{{ stats.agents }} agents</span>
              <span class="mono active-badge">{{ stats.active }} active</span>
            </div>
            <div class="dept-card-row dim">
              <span>${{ stats.spent }} today</span>
              <span>{{ stats.tasks }} tasks</span>
            </div>
          </div>
        </div>

        <!-- Graph canvas -->
        <div class="org-graph-wrapper" ref="containerRef">
          <svg ref="svgRef" class="org-svg">
            <defs>
              <filter id="org-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <g ref="mainGroupRef">
              <g ref="edgesGroupRef"></g>
              <g ref="nodesGroupRef"></g>
            </g>
          </svg>

          <!-- Agent tooltip -->
          <div
            v-if="hoveredAgent"
            class="agent-tooltip"
            :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }"
          >
            <div class="tt-name">{{ hoveredAgent.name }}</div>
            <div class="tt-role">{{ hoveredAgent.role }}</div>
            <div class="tt-status" :class="hoveredAgent.status">
              <span class="st-dot"></span>{{ hoveredAgent.status }}
            </div>
            <div v-if="hoveredAgent.currentTask" class="tt-task">▸ {{ hoveredAgent.currentTask }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import TopBar from '../components/TopBar.vue'
import Sidebar from '../components/Sidebar.vue'
import { agents, edges, departmentColors, departmentGlowColors } from '../data/mockData'
import type { Agent } from '../data/mockData'

interface OrgNode extends Agent {
  x: number
  y: number
  vx: number
  vy: number
  fx?: number | null
  fy?: number | null
  r: number
}

interface OrgLink {
  source: OrgNode
  target: OrgNode
  volume: number
}

const containerRef = ref<HTMLElement | null>(null)
const svgRef = ref<SVGElement | null>(null)
const mainGroupRef = ref<SVGGElement | null>(null)
const edgesGroupRef = ref<SVGGElement | null>(null)
const nodesGroupRef = ref<SVGGElement | null>(null)

const zoomedDept = ref<string | null>(null)
const hoveredAgent = ref<OrgNode | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

let simulation: d3.Simulation<OrgNode, OrgLink> | null = null
let dotTimers: ReturnType<typeof setInterval>[] = []

const deptColors = departmentColors

const deptStats = computed(() => {
  const stats: Record<string, { agents: number; active: number; spent: number; tasks: number }> = {}
  const depts = ['Engineering', 'Marketing', 'Finance', 'HR', 'Executive']
  depts.forEach(dept => {
    const deptAgents = agents.filter(a => a.department === dept)
    stats[dept] = {
      agents: deptAgents.length,
      active: deptAgents.filter(a => a.status === 'active').length,
      spent: Math.round(deptAgents.reduce((s, a) => s + a.totalCost * 0.056, 0)),
      tasks: deptAgents.reduce((s, a) => s + a.tasksCompleted, 0),
    }
  })
  return stats
})

function nodeRadius(agent: Agent, zoomed: boolean): number {
  if (!zoomed) {
    if (agent.level === 'CEO') return 30
    if (agent.level === 'VP') return 22
    return 14 + agent.workload * 6
  }
  if (agent.level === 'CEO') return 24
  if (agent.level === 'VP') return 18
  return 13 + agent.workload * 5
}

function zoomIntoDept(dept: string) {
  zoomedDept.value = dept
  nextTick(() => rebuildGraph())
}

function zoomOut() {
  zoomedDept.value = null
  nextTick(() => rebuildGraph())
}

onMounted(async () => {
  await nextTick()
  rebuildGraph()
})

onUnmounted(() => {
  if (simulation) simulation.stop()
  dotTimers.forEach(t => clearInterval(t))
})

function rebuildGraph() {
  if (simulation) simulation.stop()
  dotTimers.forEach(t => clearInterval(t))
  dotTimers = []

  if (!containerRef.value || !svgRef.value) return

  const container = containerRef.value
  const svgEl = svgRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  d3.select(svgEl).attr('width', width).attr('height', height)
  d3.select(edgesGroupRef.value!).selectAll('*').remove()
  d3.select(nodesGroupRef.value!).selectAll('*').remove()

  // Zoom/pan
  const zoom = d3.zoom<SVGElement, unknown>()
    .scaleExtent([0.2, 4])
    .on('zoom', event => {
      d3.select(mainGroupRef.value!).attr('transform', event.transform.toString())
    })
  d3.select(svgEl).call(zoom)

  const zoomed = zoomedDept.value
  const visibleAgents = zoomed
    ? agents.filter(a => a.department === zoomed || a.level === 'CEO')
    : agents

  const simNodes: OrgNode[] = visibleAgents.map(a => ({
    ...a,
    x: width / 2 + (Math.random() - 0.5) * 30,
    y: height / 2 + (Math.random() - 0.5) * 30,
    vx: 0,
    vy: 0,
    r: nodeRadius(a, !!zoomed),
  }))

  const nodeMap = new Map(simNodes.map(n => [n.id, n]))

  const simLinks: OrgLink[] = edges
    .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
    .map(e => ({
      source: nodeMap.get(e.source)!,
      target: nodeMap.get(e.target)!,
      volume: e.volume,
    }))

  // Department centers
  let deptCenters: Record<string, { x: number; y: number }>
  if (zoomed) {
    // Zoomed in: hierarchy layout
    deptCenters = {
      Executive: { x: width * 0.5, y: height * 0.15 },
      [zoomed]: { x: width * 0.5, y: height * 0.55 },
    }
  } else {
    deptCenters = {
      Executive: { x: width * 0.5, y: height * 0.18 },
      Engineering: { x: width * 0.22, y: height * 0.62 },
      Marketing: { x: width * 0.78, y: height * 0.62 },
      Finance: { x: width * 0.5, y: height * 0.78 },
      HR: { x: width * 0.5, y: height * 0.92 },
    }
  }

  simulation = d3.forceSimulation<OrgNode>(simNodes)
    .force('link', d3.forceLink<OrgNode, OrgLink>(simLinks)
      .id(d => d.id)
      .distance(d => zoomed ? 90 : 120)
      .strength(0.5)
    )
    .force('charge', d3.forceManyBody().strength(d => {
      if (d.level === 'CEO') return -500
      if (d.level === 'VP') return zoomed ? -300 : -400
      return zoomed ? -180 : -250
    }))
    .force('collide', d3.forceCollide<OrgNode>(d => d.r + 22))
    .force('center', d3.forceCenter(width / 2, height / 2).strength(0.04))
    .force('cluster', () => {
      for (const node of simNodes) {
        const center = deptCenters[node.department] ?? deptCenters['Executive']
        node.vx! += (center.x - node.x!) * 0.02
        node.vy! += (center.y - node.y!) * 0.02
      }
    })
    .alphaDecay(0.015)
    .velocityDecay(0.4)

  // Draw edges
  const edgesG = d3.select(edgesGroupRef.value!)
  const edgePaths = edgesG.selectAll<SVGPathElement, OrgLink>('.org-edge')
    .data(simLinks)
    .join('path')
    .attr('class', 'org-edge')
    .attr('stroke', 'rgba(139,92,246,0.2)')
    .attr('stroke-width', d => 0.5 + (d.volume / 10) * 2)
    .attr('fill', 'none')
    .attr('stroke-dasharray', '3 7')

  let dashOff = 0
  let rafId: number
  const animDashes = () => {
    dashOff -= 0.4
    edgePaths.attr('stroke-dashoffset', dashOff)
    rafId = requestAnimationFrame(animDashes)
  }
  animDashes()

  // Draw nodes
  const nodesG = d3.select(nodesGroupRef.value!)
  const nodeGroups = nodesG.selectAll<SVGGElement, OrgNode>('.org-node')
    .data(simNodes)
    .join('g')
    .attr('class', 'org-node')
    .style('cursor', d => d.department !== 'Executive' || d.level === 'CEO' ? 'pointer' : 'default')
    .call(
      d3.drag<SVGGElement, OrgNode>()
        .on('start', (e, d) => { if (!e.active) simulation!.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) simulation!.alphaTarget(0); d.fx = null; d.fy = null })
    )
    .on('mouseenter', (event, d) => {
      hoveredAgent.value = d
      tooltipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
    })
    .on('mousemove', (event) => {
      tooltipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
    })
    .on('mouseleave', () => { hoveredAgent.value = null })
    .on('click', (_, d) => {
      if (!zoomed && d.level !== 'CEO') {
        zoomIntoDept(d.department)
      }
    })

  // Glow bg
  nodeGroups.append('circle')
    .attr('r', d => d.r * 2)
    .attr('fill', d => departmentGlowColors[d.department] || 'rgba(255,255,255,0.1)')
    .attr('opacity', d => d.status === 'active' ? 0.07 : 0.02)

  // Glow ring
  nodeGroups.filter(d => d.status === 'active').append('circle')
    .attr('r', d => d.r + 8)
    .attr('fill', 'none')
    .attr('stroke', d => departmentGlowColors[d.department])
    .attr('stroke-width', 1.5)
    .attr('opacity', 0.35)

  // Main circle
  nodeGroups.append('circle')
    .attr('r', d => d.r)
    .attr('fill', d => departmentColors[d.department] || '#fff')
    .attr('fill-opacity', d => d.status === 'offline' ? 0.04 : d.status === 'idle' ? 0.1 : 0.16)
    .attr('stroke', d => departmentColors[d.department] || '#fff')
    .attr('stroke-width', d => d.level === 'CEO' ? 2.5 : 2)
    .attr('stroke-opacity', d => d.status === 'offline' ? 0.15 : d.status === 'idle' ? 0.4 : 1)
    .attr('filter', d => d.status === 'active' ? 'url(#org-glow)' : 'none')

  // Labels
  nodeGroups.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.r + 15)
    .attr('font-size', d => d.level === 'CEO' ? 12 : d.level === 'VP' ? 11 : 10)
    .attr('font-family', 'Inter, sans-serif')
    .attr('fill', d => departmentColors[d.department])
    .attr('fill-opacity', d => d.status === 'offline' ? 0.15 : d.status === 'idle' ? 0.45 : 1)
    .attr('font-weight', d => d.level === 'CEO' ? 600 : d.level === 'VP' ? 500 : 400)
    .text(d => zoomed ? d.name.split(' ')[0] : (d.level === 'CEO' || d.level === 'VP' ? d.name.split(' ')[0] : ''))

  // Dept hover hint (not zoomed, not CEO)
  if (!zoomed) {
    nodeGroups.filter(d => d.level === 'IC').append('title').text(d => `${d.department} team — click to zoom`)
  }

  // Pulsing glow
  function pulse() {
    nodesG.selectAll('circle:nth-child(2)')
      .transition().duration(2500).ease(d3.easeSinInOut).attr('opacity', 0.65)
      .transition().duration(2500).ease(d3.easeSinInOut).attr('opacity', 0.2)
      .on('end', pulse)
  }
  pulse()

  simulation.on('tick', () => {
    edgePaths.attr('d', d => {
      const s = d.source as OrgNode
      const t = d.target as OrgNode
      if (s.x == null || t.x == null) return ''
      const mx = (s.x + t.x) / 2 + (t.y - s.y) * 0.12
      const my = (s.y + t.y) / 2 - (t.x - s.x) * 0.12
      return `M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`
    })
    nodeGroups.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })

  // Cleanup on next rebuild
  const origStop = simulation.stop.bind(simulation)
  simulation.stop = () => {
    cancelAnimationFrame(rafId)
    origStop()
  }
}
</script>

<style scoped>
.org-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #08080f;
  overflow: hidden;
}

.org-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.org-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.org-toolbar {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-btn {
  background: rgba(8,8,20,0.85);
  border: 1px solid rgba(255,255,255,0.12);
  color: rgba(255,255,255,0.7);
  padding: 8px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-family: 'Inter', sans-serif;
  backdrop-filter: blur(12px);
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.back-btn:hover {
  background: rgba(59,130,246,0.12);
  border-color: rgba(59,130,246,0.3);
  color: #3b82f6;
}

.dept-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(8,8,20,0.85);
  border: 1px solid rgba(255,255,255,0.08);
  border-left: 2px solid var(--dept-col);
  padding: 8px 16px;
  border-radius: 6px;
  backdrop-filter: blur(12px);
}

.dept-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--dept-col);
}

.dept-stats {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}

.view-hint {
  background: rgba(8,8,20,0.75);
  border: 1px solid rgba(255,255,255,0.06);
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.3);
  backdrop-filter: blur(8px);
}

.dept-overlay {
  position: absolute;
  top: 60px;
  right: 20px;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dept-card {
  background: rgba(8,8,20,0.8);
  border: 1px solid rgba(255,255,255,0.07);
  border-left: 2px solid var(--dept-col);
  border-radius: 6px;
  padding: 10px 14px;
  cursor: pointer;
  backdrop-filter: blur(12px);
  transition: background 0.15s, border-color 0.15s;
  min-width: 180px;
}

.dept-card:hover {
  background: rgba(255,255,255,0.04);
  border-color: rgba(255,255,255,0.14);
}

.dept-card-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--dept-col);
  margin-bottom: 6px;
}

.dept-card-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 3px;
}

.dept-card-row.dim { color: rgba(255,255,255,0.3); }

.active-badge {
  color: #10b981;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.org-graph-wrapper {
  flex: 1;
  position: relative;
}

.org-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.agent-tooltip {
  position: absolute;
  pointer-events: none;
  background: rgba(8,8,20,0.92);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 10px 14px;
  z-index: 200;
  backdrop-filter: blur(12px);
  animation: fadeUp 0.15s ease-out;
}

.tt-name {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  margin-bottom: 3px;
}

.tt-role {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
  margin-bottom: 5px;
}

.tt-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tt-status.active { color: #10b981; }
.tt-status.idle { color: rgba(255,255,255,0.35); }
.tt-status.offline { color: rgba(255,255,255,0.2); }

.st-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.tt-task {
  font-size: 10px;
  color: rgba(255,255,255,0.35);
  margin-top: 5px;
  font-style: italic;
  max-width: 220px;
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
