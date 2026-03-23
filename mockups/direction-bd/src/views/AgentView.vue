<template>
  <div class="agent-layout">
    <TopBar />
    <div class="agent-body">
      <Sidebar />
      <div class="agent-main">
        <!-- Left Panel: Identity + Metrics -->
        <div class="identity-panel">
          <div class="identity-header">
            <div class="agent-avatar-wrap">
              <div class="agent-avatar-ring" :style="{ '--dept': deptColor }"></div>
              <div class="agent-avatar-pulse" :style="{ '--dept': deptColor }"></div>
              <div class="agent-avatar-initials" :style="{ color: deptColor }">MS</div>
            </div>
            <div class="agent-headline">
              <h2 class="agent-name">Maria Santos</h2>
              <div class="agent-role">Senior Market Analyst</div>
              <div class="agent-dept" :style="{ color: deptColor }">
                <span class="dept-dot" :style="{ background: deptColor }"></span>
                Marketing
              </div>
            </div>
          </div>

          <div class="status-autonomy-row">
            <div class="status-chip active">
              <span class="chip-dot"></span>
              Active
            </div>
            <div class="autonomy-chip">L3 Autonomous</div>
          </div>

          <div class="current-task-block">
            <div class="block-label">Current Task</div>
            <div class="current-task-text">Competitor landscape analysis — 67% complete</div>
            <div class="task-progress-bar">
              <div class="task-progress-fill" style="width: 67%"></div>
            </div>
          </div>

          <!-- Performance metrics -->
          <div class="metrics-section">
            <div class="section-title">Performance</div>
            <div class="metrics-grid">
              <div class="metric-row">
                <span class="mr-label">Tasks completed</span>
                <span class="mr-val mono">47</span>
              </div>
              <div class="metric-row">
                <span class="mr-label">Avg task time</span>
                <span class="mr-val mono">2.3h</span>
              </div>
              <div class="metric-row">
                <span class="mr-label">Success rate</span>
                <span class="mr-val mono success">94%</span>
              </div>
              <div class="metric-row">
                <span class="mr-label">Cost per task</span>
                <span class="mr-val mono">$0.82</span>
              </div>
              <div class="metric-row">
                <span class="mr-label">Total cost</span>
                <span class="mr-val mono">$38.54</span>
              </div>
            </div>

            <div class="workload-row">
              <span class="mr-label">Workload</span>
              <div class="wl-bar">
                <div class="wl-fill" style="width: 80%; --dept: #8b5cf6"></div>
              </div>
              <span class="mono dim">80%</span>
            </div>
          </div>

          <!-- Memory mutations -->
          <div class="memory-section">
            <div class="section-title">
              <span>Memory</span>
              <span class="section-badge mono">{{ mariaMemory.length }}</span>
            </div>
            <div class="memory-list">
              <div v-for="mem in mariaMemory" :key="mem.id" class="memory-item" :class="mem.type.toLowerCase()">
                <span class="mem-type">{{ mem.type }}</span>
                <span class="mem-content">{{ mem.content }}</span>
                <span class="mem-time mono">{{ mem.time }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Panel: Ego-network + Outputs -->
        <div class="ego-panel">
          <!-- Ego network -->
          <div class="ego-graph-wrap" ref="egoContainerRef">
            <div class="ego-title">Collaboration Network</div>
            <svg ref="egoSvgRef" class="ego-svg">
              <defs>
                <filter id="ego-glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="4" result="b" />
                  <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
              </defs>
              <g ref="egoEdgesRef"></g>
              <g ref="egoNodesRef"></g>
            </svg>

            <!-- Edge tooltip -->
            <div v-if="hoveredEdgeInfo" class="ego-edge-tooltip"
              :style="{ left: egoTipPos.x + 'px', top: egoTipPos.y + 'px' }">
              <div class="tt-rel">{{ hoveredEdgeInfo.relationshipType }}</div>
              <div class="tt-vol mono">{{ hoveredEdgeInfo.volume * 10 }} messages / day</div>
              <div class="tt-last">Last: {{ hoveredEdgeInfo.lastInteraction }}</div>
            </div>

            <!-- Node tooltip -->
            <div v-if="hoveredEgoNode && hoveredEgoNode.id !== 'mktg-analyst'" class="ego-node-tooltip"
              :style="{ left: egoTipPos.x + 'px', top: egoTipPos.y + 'px' }">
              <div class="tt-name">{{ hoveredEgoNode.name }}</div>
              <div class="tt-role">{{ hoveredEgoNode.role }}</div>
              <div class="tt-dept" :style="{ color: deptColor_(hoveredEgoNode.department) }">{{ hoveredEgoNode.department }}</div>
            </div>
          </div>

          <!-- Recent outputs -->
          <div class="outputs-section">
            <div class="section-title">Recent Outputs</div>
            <div class="output-list">
              <div v-for="output in mariaOutputs" :key="output.id" class="output-card">
                <div class="output-card-left">
                  <div class="output-type-badge">{{ output.type }}</div>
                  <div class="output-title">{{ output.title }}</div>
                  <div class="output-meta">
                    <span class="mono dim">{{ output.time }}</span>
                    <span class="output-dot">·</span>
                    <span class="mono dim">{{ output.tokens.toLocaleString() }} tokens</span>
                  </div>
                </div>
                <div class="output-card-actions">
                  <button class="output-btn">View</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import TopBar from '../components/TopBar.vue'
import Sidebar from '../components/Sidebar.vue'
import { agents, edges, mariaMemory, mariaOutputs, departmentColors, departmentGlowColors } from '../data/mockData'
import type { Agent, Edge } from '../data/mockData'

const deptColor = '#8b5cf6'

function deptColor_(dept: string): string {
  return departmentColors[dept] || '#ffffff'
}

const egoContainerRef = ref<HTMLElement | null>(null)
const egoSvgRef = ref<SVGElement | null>(null)
const egoEdgesRef = ref<SVGGElement | null>(null)
const egoNodesRef = ref<SVGGElement | null>(null)

interface EgoNode extends Agent {
  x: number
  y: number
  vx: number
  vy: number
  fx?: number | null
  fy?: number | null
  r: number
  isCenter: boolean
}

interface EgoLink {
  source: EgoNode
  target: EgoNode
  volume: number
  frequency: number
  lastInteraction: string
  relationshipType: string
}

const hoveredEdgeInfo = ref<Edge | null>(null)
const hoveredEgoNode = ref<EgoNode | null>(null)
const egoTipPos = ref({ x: 0, y: 0 })

let simulation: d3.Simulation<EgoNode, EgoLink> | null = null
let rafId: number | null = null

onMounted(async () => {
  await nextTick()
  buildEgoGraph()
})

onUnmounted(() => {
  if (simulation) simulation.stop()
  if (rafId) cancelAnimationFrame(rafId)
})

function buildEgoGraph() {
  if (!egoContainerRef.value || !egoSvgRef.value) return

  const container = egoContainerRef.value
  const svgEl = egoSvgRef.value
  const width = container.clientWidth
  const height = container.clientHeight - 36

  d3.select(svgEl).attr('width', width).attr('height', height)

  // Build ego network for Maria (mktg-analyst)
  const mariaId = 'mktg-analyst'
  const connectedEdges = edges.filter(e => e.source === mariaId || e.target === mariaId)
  const connectedIds = new Set<string>()
  connectedEdges.forEach(e => {
    connectedIds.add(e.source)
    connectedIds.add(e.target)
  })

  const egoAgents = agents.filter(a => connectedIds.has(a.id))

  const egoNodes: EgoNode[] = egoAgents.map(a => ({
    ...a,
    x: a.id === mariaId ? width / 2 : width / 2 + (Math.random() - 0.5) * 30,
    y: a.id === mariaId ? height / 2 : height / 2 + (Math.random() - 0.5) * 30,
    vx: 0,
    vy: 0,
    r: a.id === mariaId ? 22 : (a.level === 'CEO' ? 18 : a.level === 'VP' ? 15 : 11),
    isCenter: a.id === mariaId,
  }))

  const nodeMap = new Map(egoNodes.map(n => [n.id, n]))

  const egoLinks: EgoLink[] = connectedEdges.map(e => ({
    source: nodeMap.get(e.source)!,
    target: nodeMap.get(e.target)!,
    volume: e.volume,
    frequency: e.frequency,
    lastInteraction: e.lastInteraction,
    relationshipType: e.relationshipType,
  })).filter(l => l.source && l.target)

  // Fix center node
  const centerNode = nodeMap.get(mariaId)!
  centerNode.fx = width / 2
  centerNode.fy = height / 2

  simulation = d3.forceSimulation<EgoNode>(egoNodes)
    .force('link', d3.forceLink<EgoNode, EgoLink>(egoLinks)
      .id(d => d.id)
      .distance(d => 90 + (10 - d.volume) * 5)
      .strength(0.6)
    )
    .force('charge', d3.forceManyBody().strength(-250))
    .force('collide', d3.forceCollide<EgoNode>(d => d.r + 18))
    .alphaDecay(0.02)
    .velocityDecay(0.4)

  // Draw edges
  const edgesG = d3.select(egoEdgesRef.value!)
  const egoEdgePaths = edgesG.selectAll<SVGPathElement, EgoLink>('.ego-edge')
    .data(egoLinks)
    .join('path')
    .attr('class', 'ego-edge')
    .attr('stroke', 'rgba(139,92,246,0.3)')
    .attr('stroke-width', d => 0.5 + (d.volume / 10) * 3)
    .attr('fill', 'none')
    .attr('stroke-dasharray', '4 7')
    .style('cursor', 'pointer')
    .on('mouseenter', (event, d) => {
      hoveredEdgeInfo.value = {
        source: (d.source as EgoNode).id,
        target: (d.target as EgoNode).id,
        volume: d.volume,
        frequency: d.frequency,
        lastInteraction: d.lastInteraction,
        relationshipType: d.relationshipType,
      }
      egoTipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
      d3.select(event.currentTarget as SVGPathElement).attr('stroke', 'rgba(139,92,246,0.7)')
    })
    .on('mousemove', event => { egoTipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 } })
    .on('mouseleave', event => {
      hoveredEdgeInfo.value = null
      d3.select(event.currentTarget as SVGPathElement).attr('stroke', 'rgba(139,92,246,0.3)')
    })

  let dashOff = 0
  const animDashes = () => {
    dashOff -= 0.4
    egoEdgePaths.attr('stroke-dashoffset', dashOff)
    rafId = requestAnimationFrame(animDashes)
  }
  animDashes()

  // Draw nodes
  const nodesG = d3.select(egoNodesRef.value!)
  const nodeGroups = nodesG.selectAll<SVGGElement, EgoNode>('.ego-node')
    .data(egoNodes)
    .join('g')
    .attr('class', 'ego-node')
    .style('cursor', 'pointer')
    .call(
      d3.drag<SVGGElement, EgoNode>()
        .on('start', (e, d) => { if (!e.active) simulation!.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { if (!d.isCenter) { d.fx = e.x; d.fy = e.y } })
        .on('end', (e, d) => { if (!e.active) simulation!.alphaTarget(0); if (!d.isCenter) { d.fx = null; d.fy = null } })
    )
    .on('mouseenter', (event, d) => {
      hoveredEgoNode.value = d
      egoTipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
    })
    .on('mousemove', event => { egoTipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 } })
    .on('mouseleave', () => { hoveredEgoNode.value = null })

  // Glow bg
  nodeGroups.append('circle')
    .attr('r', d => d.r * 2)
    .attr('fill', d => departmentGlowColors[d.department])
    .attr('opacity', d => d.isCenter ? 0.12 : 0.05)

  // Glow ring for center
  nodeGroups.filter(d => d.isCenter).append('circle')
    .attr('r', d => d.r + 10)
    .attr('fill', 'none')
    .attr('stroke', '#8b5cf6')
    .attr('stroke-width', 2)
    .attr('opacity', 0.5)

  // Outer pulse ring for center
  nodeGroups.filter(d => d.isCenter).append('circle')
    .attr('r', d => d.r + 4)
    .attr('fill', 'none')
    .attr('stroke', '#8b5cf6')
    .attr('stroke-width', 1)
    .attr('opacity', 0)

  // Main circle
  nodeGroups.append('circle')
    .attr('r', d => d.r)
    .attr('fill', d => departmentColors[d.department])
    .attr('fill-opacity', d => d.isCenter ? 0.22 : 0.14)
    .attr('stroke', d => departmentColors[d.department])
    .attr('stroke-width', d => d.isCenter ? 2.5 : 1.5)
    .attr('filter', d => d.isCenter ? 'url(#ego-glow)' : 'none')

  // Name labels
  nodeGroups.append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.r + 14)
    .attr('font-size', d => d.isCenter ? 11 : 9)
    .attr('font-family', 'Inter, sans-serif')
    .attr('fill', d => departmentColors[d.department])
    .attr('font-weight', d => d.isCenter ? 600 : 400)
    .text(d => d.name.split(' ')[0])

  // Pulsing center
  function pulseCenter() {
    nodesG.selectAll<SVGCircleElement, EgoNode>('circle:nth-child(3)')
      .filter((d): boolean => d.isCenter)
      .attr('opacity', 0.5)
      .attr('r', d => d.r + 4)
      .transition()
      .duration(2000)
      .ease(d3.easeExpOut)
      .attr('r', d => d.r + 45)
      .attr('opacity', 0)
      .on('end', () => setTimeout(pulseCenter, 1800))
  }
  setTimeout(pulseCenter, 600)

  // Glow ring breathing
  function breathe() {
    nodesG.selectAll<SVGCircleElement, EgoNode>('circle:nth-child(2)')
      .filter((d): boolean => d.isCenter)
      .transition().duration(2500).ease(d3.easeSinInOut).attr('opacity', 0.8)
      .transition().duration(2500).ease(d3.easeSinInOut).attr('opacity', 0.3)
      .on('end', breathe)
  }
  breathe()

  simulation.on('tick', () => {
    egoEdgePaths.attr('d', d => {
      const s = d.source as EgoNode
      const t = d.target as EgoNode
      if (s.x == null || t.x == null) return ''
      return `M${s.x},${s.y} L${t.x},${t.y}`
    })
    nodeGroups.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })
}
</script>

<style scoped>
.agent-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #08080f;
  overflow: hidden;
}

.agent-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.agent-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  gap: 0;
}

/* ===== Left Panel ===== */
.identity-panel {
  width: 40%;
  max-width: 380px;
  border-right: 1px solid rgba(255,255,255,0.07);
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
  padding: 24px 20px;
}

.identity-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.agent-avatar-wrap {
  position: relative;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-avatar-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--dept, #8b5cf6);
  box-shadow: 0 0 16px var(--dept, rgba(139,92,246,0.5));
  animation: ringPulseAnim 3s ease-in-out infinite;
}

.agent-avatar-pulse {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 1px solid var(--dept, #8b5cf6);
  opacity: 0;
  animation: outerPulse 2.5s ease-out infinite;
}

.agent-avatar-initials {
  font-size: 20px;
  font-weight: 700;
  z-index: 1;
  position: relative;
  letter-spacing: -0.5px;
}

.agent-headline {
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 18px;
  font-weight: 700;
  color: rgba(255,255,255,0.92);
  margin-bottom: 4px;
  letter-spacing: -0.3px;
}

.agent-role {
  font-size: 12px;
  color: rgba(255,255,255,0.45);
  margin-bottom: 5px;
}

.agent-dept {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
}

.dept-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-autonomy-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.status-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 20px;
  font-weight: 500;
  letter-spacing: 0.3px;
}

.status-chip.active {
  background: rgba(16,185,129,0.12);
  color: #10b981;
  border: 1px solid rgba(16,185,129,0.25);
}

.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
  animation: chipDotPulse 2s ease-in-out infinite;
}

.autonomy-chip {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(59,130,246,0.1);
  color: #3b82f6;
  border: 1px solid rgba(59,130,246,0.2);
  font-weight: 500;
}

.current-task-block {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 20px;
}

.block-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(255,255,255,0.3);
  margin-bottom: 6px;
}

.current-task-text {
  font-size: 12px;
  color: rgba(255,255,255,0.65);
  margin-bottom: 10px;
  line-height: 1.4;
}

.task-progress-bar {
  height: 3px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
}

.task-progress-fill {
  height: 100%;
  background: #8b5cf6;
  box-shadow: 0 0 6px rgba(139,92,246,0.5);
  border-radius: 2px;
}

.metrics-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(255,255,255,0.3);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-badge {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.4);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 9px;
}

.metrics-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.mr-label {
  font-size: 11px;
  color: rgba(255,255,255,0.4);
}

.mr-val {
  font-size: 13px;
  color: rgba(255,255,255,0.8);
  font-weight: 500;
}

.mr-val.success {
  color: #10b981;
}

.mono { font-family: 'JetBrains Mono', monospace; }
.dim { color: rgba(255,255,255,0.3); }

.workload-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.wl-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
}

.wl-fill {
  height: 100%;
  background: var(--dept, #8b5cf6);
  box-shadow: 0 0 6px var(--dept, rgba(139,92,246,0.5));
  border-radius: 2px;
}

/* Memory */
.memory-section { flex: 1; min-height: 0; }

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.memory-item {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: background 0.15s;
}

.memory-item:hover {
  background: rgba(255,255,255,0.04);
}

.memory-item.learned { border-left: 2px solid #10b981; }
.memory-item.updated { border-left: 2px solid #3b82f6; }
.memory-item.stored { border-left: 2px solid #8b5cf6; }

.mem-type {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-weight: 600;
  color: rgba(255,255,255,0.3);
}

.memory-item.learned .mem-type { color: #10b981; }
.memory-item.updated .mem-type { color: #3b82f6; }
.memory-item.stored .mem-type { color: #8b5cf6; }

.mem-content {
  font-size: 11px;
  color: rgba(255,255,255,0.65);
  line-height: 1.4;
}

.mem-time {
  font-size: 9px;
  color: rgba(255,255,255,0.25);
}

/* ===== Right Panel ===== */
.ego-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ego-graph-wrap {
  flex: 1;
  position: relative;
  min-height: 0;
  background: rgba(255,255,255,0.008);
}

.ego-title {
  position: absolute;
  top: 16px;
  left: 16px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(255,255,255,0.25);
  z-index: 10;
}

.ego-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.ego-edge-tooltip,
.ego-node-tooltip {
  position: absolute;
  pointer-events: none;
  background: rgba(8,8,20,0.92);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 10px 14px;
  z-index: 200;
  backdrop-filter: blur(12px);
  min-width: 150px;
}

.tt-rel {
  font-size: 12px;
  font-weight: 600;
  color: #8b5cf6;
  margin-bottom: 4px;
}

.tt-vol {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  margin-bottom: 3px;
}

.tt-last {
  font-size: 10px;
  color: rgba(255,255,255,0.3);
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
  margin-bottom: 4px;
}

.tt-dept {
  font-size: 11px;
  font-weight: 500;
}

/* Outputs */
.outputs-section {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.01);
  flex-shrink: 0;
}

.output-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.output-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 10px 14px;
  transition: background 0.15s, border-color 0.15s;
}

.output-card:hover {
  background: rgba(255,255,255,0.045);
  border-color: rgba(255,255,255,0.1);
}

.output-card-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.output-type-badge {
  display: inline-block;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: #8b5cf6;
  background: rgba(139,92,246,0.1);
  padding: 1px 6px;
  border-radius: 10px;
  margin-bottom: 2px;
  align-self: flex-start;
}

.output-title {
  font-size: 13px;
  font-weight: 500;
  color: rgba(255,255,255,0.75);
}

.output-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
}

.output-dot {
  color: rgba(255,255,255,0.2);
}

.output-btn {
  background: rgba(59,130,246,0.08);
  border: 1px solid rgba(59,130,246,0.2);
  color: #3b82f6;
  font-size: 11px;
  padding: 5px 12px;
  border-radius: 5px;
  cursor: pointer;
  font-family: 'Inter', sans-serif;
  transition: background 0.15s, border-color 0.15s;
}

.output-btn:hover {
  background: rgba(59,130,246,0.16);
  border-color: rgba(59,130,246,0.4);
}

/* Animations */
@keyframes ringPulseAnim {
  0%, 100% { box-shadow: 0 0 10px var(--dept, rgba(139,92,246,0.4)); opacity: 0.8; }
  50% { box-shadow: 0 0 22px var(--dept, rgba(139,92,246,0.7)); opacity: 1; }
}

@keyframes outerPulse {
  0% { transform: scale(1); opacity: 0.4; }
  60% { transform: scale(1.5); opacity: 0; }
  100% { transform: scale(1.5); opacity: 0; }
}

@keyframes chipDotPulse {
  0%, 100% { box-shadow: 0 0 5px #10b981; }
  50% { box-shadow: 0 0 12px #10b981; }
}
</style>
