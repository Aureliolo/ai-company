<template>
  <div class="force-graph-container" ref="containerRef">
    <svg ref="svgRef" class="force-svg">
      <defs>
        <filter id="glow-blue" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="glow-violet" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="glow-strong" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="rgba(139,92,246,0.4)" />
        </marker>
      </defs>
      <!-- Edge group -->
      <g class="edges-group" ref="edgesGroupRef"></g>
      <!-- Traveling dots group -->
      <g class="dots-group" ref="dotsGroupRef"></g>
      <!-- Node group -->
      <g class="nodes-group" ref="nodesGroupRef"></g>
    </svg>

    <!-- Node tooltip -->
    <div
      v-if="hoveredNode"
      class="node-tooltip"
      :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }"
    >
      <div class="tooltip-name">{{ hoveredNode.name }}</div>
      <div class="tooltip-role">{{ hoveredNode.role }}</div>
      <div class="tooltip-status" :class="hoveredNode.status">
        <span class="status-dot"></span>
        {{ hoveredNode.status }}
      </div>
      <div v-if="hoveredNode.currentTask" class="tooltip-task">
        ▸ {{ hoveredNode.currentTask }}
      </div>
    </div>

    <!-- Edge tooltip -->
    <div
      v-if="hoveredEdge"
      class="edge-tooltip"
      :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }"
    >
      <div class="tooltip-rel">{{ hoveredEdge.relationshipType }}</div>
      <div class="tooltip-vol">{{ hoveredEdge.volume * 10 }} messages/day</div>
      <div class="tooltip-last">Last: {{ hoveredEdge.lastInteraction }}</div>
    </div>

    <!-- Detail panel -->
    <transition name="slide-panel">
      <div v-if="selectedNode" class="detail-panel animate-slide-in-right">
        <button class="panel-close" @click="selectedNode = null">✕</button>
        <div class="panel-agent-header">
          <div class="panel-avatar" :style="{ '--dept-color': deptColor(selectedNode) }">
            <div class="panel-avatar-ring"></div>
            <span class="panel-avatar-initials">{{ initials(selectedNode.name) }}</span>
          </div>
          <div class="panel-agent-info">
            <div class="panel-name">{{ selectedNode.name }}</div>
            <div class="panel-role">{{ selectedNode.role }}</div>
            <div class="panel-dept" :style="{ color: deptColor(selectedNode) }">{{ selectedNode.department }}</div>
          </div>
        </div>
        <div class="panel-status-row">
          <span class="status-badge" :class="selectedNode.status">{{ selectedNode.status }}</span>
          <span class="autonomy-badge">{{ selectedNode.autonomy }}</span>
        </div>
        <div v-if="selectedNode.currentTask" class="panel-task">
          <span class="panel-task-label">Current task</span>
          <span class="panel-task-text">{{ selectedNode.currentTask }}</span>
        </div>
        <div class="panel-metrics">
          <div class="metric-card">
            <span class="metric-val mono">{{ selectedNode.tasksCompleted }}</span>
            <span class="metric-label">Tasks done</span>
          </div>
          <div class="metric-card">
            <span class="metric-val mono">{{ selectedNode.avgTaskTime }}h</span>
            <span class="metric-label">Avg time</span>
          </div>
          <div class="metric-card">
            <span class="metric-val mono">{{ selectedNode.successRate }}%</span>
            <span class="metric-label">Success</span>
          </div>
          <div class="metric-card">
            <span class="metric-val mono">${{ selectedNode.costPerTask }}</span>
            <span class="metric-label">Cost/task</span>
          </div>
        </div>
        <div class="panel-workload">
          <span class="workload-label">Workload</span>
          <div class="workload-bar">
            <div class="workload-fill" :style="{ width: (selectedNode.workload * 100) + '%', '--dept-color': deptColor(selectedNode) }"></div>
          </div>
          <span class="workload-pct mono">{{ Math.round(selectedNode.workload * 100) }}%</span>
        </div>
        <router-link to="/agent" class="panel-view-link" @click="selectedNode = null">
          View full profile →
        </router-link>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import { agents, edges, departmentColors, departmentGlowColors } from '../data/mockData'
import type { Agent, Edge } from '../data/mockData'

interface SimNode extends Agent {
  x: number
  y: number
  vx: number
  vy: number
  fx?: number | null
  fy?: number | null
  r: number
}

interface SimLink {
  source: SimNode
  target: SimNode
  volume: number
  frequency: number
  lastInteraction: string
  relationshipType: string
}

const containerRef = ref<HTMLElement | null>(null)
const svgRef = ref<SVGElement | null>(null)
const edgesGroupRef = ref<SVGGElement | null>(null)
const dotsGroupRef = ref<SVGGElement | null>(null)
const nodesGroupRef = ref<SVGGElement | null>(null)

const hoveredNode = ref<SimNode | null>(null)
const hoveredEdge = ref<Edge | null>(null)
const selectedNode = ref<SimNode | null>(null)
const tooltipPos = ref({ x: 0, y: 0 })

let simulation: d3.Simulation<SimNode, SimLink> | null = null
let animFrameId: number | null = null
let dotTimers: ReturnType<typeof setInterval>[] = []

function deptColor(agent: { department: string }): string {
  return departmentColors[agent.department] || '#ffffff'
}

function initials(name: string): string {
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}

function nodeRadius(agent: Agent): number {
  if (agent.level === 'CEO') return 28
  if (agent.level === 'VP') return 20
  return 13 + agent.workload * 5
}

function nodeOpacity(agent: Agent): number {
  if (agent.status === 'offline') return 0.15
  if (agent.status === 'idle') return 0.45
  return 1
}

onMounted(async () => {
  await nextTick()
  if (!containerRef.value || !svgRef.value) return
  initGraph()
})

onUnmounted(() => {
  if (simulation) simulation.stop()
  if (animFrameId) cancelAnimationFrame(animFrameId)
  dotTimers.forEach(t => clearInterval(t))
})

function initGraph() {
  const container = containerRef.value!
  const svgEl = svgRef.value!
  const width = container.clientWidth
  const height = container.clientHeight

  const svg = d3.select(svgEl)
    .attr('width', width)
    .attr('height', height)

  // Add zoom/pan
  const zoomG = d3.select(svgEl)
  const zoom = d3.zoom<SVGElement, unknown>()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => {
      d3.select(edgesGroupRef.value!).attr('transform', event.transform.toString())
      d3.select(dotsGroupRef.value!).attr('transform', event.transform.toString())
      d3.select(nodesGroupRef.value!).attr('transform', event.transform.toString())
    })
  svg.call(zoom)

  // Prepare sim nodes
  const simNodes: SimNode[] = agents.map(a => ({
    ...a,
    x: width / 2 + (Math.random() - 0.5) * 20,
    y: height / 2 + (Math.random() - 0.5) * 20,
    vx: 0,
    vy: 0,
    r: nodeRadius(a),
  }))

  const nodeMap = new Map(simNodes.map(n => [n.id, n]))

  const simLinks: SimLink[] = edges
    .map(e => {
      const s = nodeMap.get(e.source)
      const t = nodeMap.get(e.target)
      if (!s || !t) return null
      return {
        source: s,
        target: t,
        volume: e.volume,
        frequency: e.frequency,
        lastInteraction: e.lastInteraction,
        relationshipType: e.relationshipType,
      }
    })
    .filter((l): l is SimLink => l !== null)

  // Department clustering forces
  const deptCenters: Record<string, { x: number; y: number }> = {
    Executive: { x: width * 0.5, y: height * 0.2 },
    Engineering: { x: width * 0.25, y: height * 0.6 },
    Marketing: { x: width * 0.75, y: height * 0.6 },
    Finance: { x: width * 0.5, y: height * 0.75 },
    HR: { x: width * 0.5, y: height * 0.9 },
  }

  simulation = d3.forceSimulation<SimNode>(simNodes)
    .force('link', d3.forceLink<SimNode, SimLink>(simLinks)
      .id(d => d.id)
      .distance(d => {
        if (d.source.level === 'CEO' || d.target.level === 'CEO') return 130
        if (d.source.level === 'VP' || d.target.level === 'VP') return 95
        return 70
      })
      .strength(0.5)
    )
    .force('charge', d3.forceManyBody().strength(d => {
      if (d.level === 'CEO') return -600
      if (d.level === 'VP') return -350
      return -200
    }))
    .force('collide', d3.forceCollide<SimNode>(d => d.r + 20))
    .force('center', d3.forceCenter(width / 2, height / 2).strength(0.05))
    .force('cluster', () => {
      for (const node of simNodes) {
        const center = deptCenters[node.department]
        if (!center) continue
        node.vx! += (center.x - node.x!) * 0.015
        node.vy! += (center.y - node.y!) * 0.015
      }
    })
    .alphaDecay(0.015)
    .velocityDecay(0.4)

  // Draw edges
  const edgesG = d3.select(edgesGroupRef.value!)
  const edgePaths = edgesG.selectAll<SVGPathElement, SimLink>('.edge')
    .data(simLinks)
    .join('path')
    .attr('class', 'edge')
    .attr('stroke', 'rgba(139,92,246,0.25)')
    .attr('stroke-width', d => 0.5 + (d.volume / 10) * 2.5)
    .attr('fill', 'none')
    .attr('stroke-dasharray', '4 8')
    .style('cursor', 'pointer')
    .on('mouseenter', (event, d) => {
      hoveredEdge.value = {
        source: (d.source as SimNode).id,
        target: (d.target as SimNode).id,
        volume: d.volume,
        frequency: d.frequency,
        lastInteraction: d.lastInteraction,
        relationshipType: d.relationshipType,
      }
      tooltipPos.value = { x: event.offsetX + 12, y: event.offsetY - 10 }
      d3.select(event.currentTarget as SVGPathElement)
        .attr('stroke', 'rgba(139,92,246,0.6)')
    })
    .on('mousemove', (event) => {
      tooltipPos.value = { x: event.offsetX + 12, y: event.offsetY - 10 }
    })
    .on('mouseleave', (event) => {
      hoveredEdge.value = null
      d3.select(event.currentTarget as SVGPathElement)
        .attr('stroke', 'rgba(139,92,246,0.25)')
    })

  // Animated dashes on edges
  let dashOffset = 0
  const animateDashes = () => {
    dashOffset -= 0.5
    edgePaths.attr('stroke-dashoffset', dashOffset)
    animFrameId = requestAnimationFrame(animateDashes)
  }
  animateDashes()

  // Draw traveling dots per edge
  const dotsG = d3.select(dotsGroupRef.value!)

  function spawnDot(link: SimLink) {
    const dot = dotsG.append('circle')
      .attr('r', 2.5)
      .attr('fill', '#8b5cf6')
      .attr('opacity', 0.9)
      .attr('filter', 'url(#glow-violet)')

    const duration = (2000 - link.frequency * 1400) + 400
    let startTime = performance.now()

    const animDot = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1)
      const s = link.source as SimNode
      const tg = link.target as SimNode
      if (s.x == null || tg.x == null) return

      // Quadratic bezier midpoint
      const mx = (s.x + tg.x) / 2 + (tg.y - s.y) * 0.15
      const my = (s.y + tg.y) / 2 - (tg.x - s.x) * 0.15

      const x = (1 - t) * (1 - t) * s.x + 2 * (1 - t) * t * mx + t * t * tg.x
      const y = (1 - t) * (1 - t) * s.y + 2 * (1 - t) * t * my + t * t * tg.y

      dot.attr('cx', x).attr('cy', y).attr('opacity', t < 0.1 ? t * 10 : t > 0.85 ? (1 - t) / 0.15 : 0.9)

      if (t < 1) {
        requestAnimationFrame(animDot)
      } else {
        dot.remove()
      }
    }
    requestAnimationFrame(animDot)
  }

  // Spawn dots at intervals based on frequency
  simLinks.forEach(link => {
    const interval = Math.round(1800 - link.frequency * 1200)
    const timer = setInterval(() => spawnDot(link), interval + Math.random() * 600)
    dotTimers.push(timer)
    // Immediate first spawn
    setTimeout(() => spawnDot(link), Math.random() * 1000)
  })

  // Draw nodes
  const nodesG = d3.select(nodesGroupRef.value!)
  const nodeGroups = nodesG.selectAll<SVGGElement, SimNode>('.node-group')
    .data(simNodes)
    .join('g')
    .attr('class', 'node-group')
    .style('cursor', 'pointer')
    .call(
      d3.drag<SVGGElement, SimNode>()
        .on('start', (event, d) => {
          if (!event.active) simulation!.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation!.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )
    .on('mouseenter', (event, d) => {
      hoveredNode.value = d
      tooltipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
    })
    .on('mousemove', (event) => {
      tooltipPos.value = { x: event.offsetX + 14, y: event.offsetY - 10 }
    })
    .on('mouseleave', () => {
      hoveredNode.value = null
    })
    .on('click', (event, d) => {
      event.stopPropagation()
      selectedNode.value = d
      hoveredNode.value = null
    })

  // Outer glow ring for active nodes
  nodeGroups
    .filter(d => d.status === 'active')
    .append('circle')
    .attr('class', 'node-glow-ring')
    .attr('r', d => d.r + 8)
    .attr('fill', 'none')
    .attr('stroke', d => departmentGlowColors[d.department] || 'rgba(255,255,255,0.3)')
    .attr('stroke-width', 1.5)
    .attr('opacity', 0.4)

  // Pulsing ring animation for CEO
  nodeGroups
    .filter(d => d.level === 'CEO')
    .append('circle')
    .attr('class', 'node-pulse-ring')
    .attr('r', d => d.r + 16)
    .attr('fill', 'none')
    .attr('stroke', d => departmentGlowColors[d.department])
    .attr('stroke-width', 1)
    .attr('opacity', 0)

  // Node background (glow layer)
  nodeGroups.append('circle')
    .attr('class', 'node-bg-glow')
    .attr('r', d => d.r * 1.8)
    .attr('fill', d => departmentGlowColors[d.department] || 'rgba(255,255,255,0.1)')
    .attr('opacity', d => {
      if (d.status === 'offline') return 0.02
      if (d.status === 'idle') return 0.04
      return 0.08
    })

  // Main node circle
  nodeGroups.append('circle')
    .attr('class', 'node-circle')
    .attr('r', d => d.r)
    .attr('fill', d => {
      const color = departmentColors[d.department] || '#ffffff'
      // Parse and darken for fill
      return color
    })
    .attr('fill-opacity', d => {
      if (d.status === 'offline') return 0.05
      if (d.status === 'idle') return 0.12
      return 0.18
    })
    .attr('stroke', d => departmentColors[d.department] || '#ffffff')
    .attr('stroke-width', d => d.level === 'CEO' ? 2.5 : d.level === 'VP' ? 2 : 1.5)
    .attr('stroke-opacity', d => nodeOpacity(d))
    .attr('filter', d => d.status === 'active' ? 'url(#glow-blue)' : 'none')

  // Node label (name)
  nodeGroups.append('text')
    .attr('class', 'node-label')
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.r + 14)
    .attr('font-size', d => d.level === 'CEO' ? 11 : d.level === 'VP' ? 10 : 9)
    .attr('font-family', 'Inter, sans-serif')
    .attr('fill', d => departmentColors[d.department] || '#ffffff')
    .attr('fill-opacity', d => nodeOpacity(d))
    .attr('font-weight', d => d.level === 'CEO' ? 600 : d.level === 'VP' ? 500 : 400)
    .text(d => d.name.split(' ')[0])

  // Role label for CEO and VPs
  nodeGroups
    .filter(d => d.level !== 'IC')
    .append('text')
    .attr('class', 'node-role')
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.r + 26)
    .attr('font-size', 8)
    .attr('font-family', 'JetBrains Mono, monospace')
    .attr('fill', 'rgba(255,255,255,0.3)')
    .text(d => d.level)

  // Pulsing animation for active nodes
  function pulseNodes() {
    nodesG.selectAll<SVGCircleElement, SimNode>('.node-glow-ring')
      .transition()
      .duration(2500)
      .ease(d3.easeSinInOut)
      .attr('opacity', 0.7)
      .transition()
      .duration(2500)
      .ease(d3.easeSinInOut)
      .attr('opacity', 0.2)
      .on('end', pulseNodes)
  }
  pulseNodes()

  // CEO pulse ring
  function pulseCEORing() {
    nodesG.selectAll<SVGCircleElement, SimNode>('.node-pulse-ring')
      .attr('opacity', 0.5)
      .attr('r', function(d) { return d.r + 4 })
      .transition()
      .duration(2000)
      .ease(d3.easeExpOut)
      .attr('r', d => d.r + 50)
      .attr('opacity', 0)
      .on('end', () => setTimeout(pulseCEORing, 1500))
  }
  setTimeout(pulseCEORing, 500)

  // Sim tick
  simulation.on('tick', () => {
    edgePaths.attr('d', d => {
      const s = d.source as SimNode
      const t = d.target as SimNode
      if (s.x == null || t.x == null) return ''
      const mx = (s.x + t.x) / 2 + (t.y - s.y) * 0.15
      const my = (s.y + t.y) / 2 - (t.x - s.x) * 0.15
      return `M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`
    })

    nodeGroups.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
  })

  // Click outside to deselect
  d3.select(svgEl).on('click', () => {
    selectedNode.value = null
  })
}
</script>

<style scoped>
.force-graph-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #08080f;
}

.force-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.node-tooltip,
.edge-tooltip {
  position: absolute;
  pointer-events: none;
  background: rgba(8,8,20,0.92);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 10px 14px;
  min-width: 160px;
  backdrop-filter: blur(12px);
  z-index: 200;
  animation: fadeSlideUp 0.15s ease-out;
}

.tooltip-name {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  margin-bottom: 3px;
}

.tooltip-role {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  margin-bottom: 6px;
}

.tooltip-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tooltip-status.active { color: #10b981; }
.tooltip-status.idle { color: rgba(255,255,255,0.35); }
.tooltip-status.offline { color: rgba(255,255,255,0.2); }

.tooltip-status .status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.tooltip-task {
  font-size: 10px;
  color: rgba(255,255,255,0.4);
  margin-top: 6px;
  font-style: italic;
  max-width: 200px;
}

.tooltip-rel {
  font-size: 12px;
  font-weight: 500;
  color: #8b5cf6;
  margin-bottom: 4px;
}

.tooltip-vol {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  font-family: 'JetBrains Mono', monospace;
}

.tooltip-last {
  font-size: 10px;
  color: rgba(255,255,255,0.3);
  margin-top: 4px;
}

/* Detail panel */
.detail-panel {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 300px;
  background: rgba(8,8,20,0.96);
  border-left: 1px solid rgba(255,255,255,0.08);
  padding: 24px 20px;
  overflow-y: auto;
  z-index: 150;
  backdrop-filter: blur(20px);
}

.panel-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: transparent;
  border: none;
  color: rgba(255,255,255,0.3);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}

.panel-close:hover {
  color: rgba(255,255,255,0.7);
  background: rgba(255,255,255,0.06);
}

.panel-agent-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  padding-right: 32px;
}

.panel-avatar {
  position: relative;
  width: 52px;
  height: 52px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-avatar-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--dept-color, #3b82f6);
  box-shadow: 0 0 12px var(--dept-color, rgba(59,130,246,0.5));
  animation: glowPulseRing 3s ease-in-out infinite;
}

.panel-avatar-initials {
  font-size: 16px;
  font-weight: 600;
  color: var(--dept-color, #3b82f6);
  z-index: 1;
  position: relative;
}

.panel-name {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  margin-bottom: 3px;
}

.panel-role {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  margin-bottom: 3px;
}

.panel-dept {
  font-size: 11px;
  font-weight: 500;
}

.panel-status-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.status-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 20px;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.status-badge.active {
  background: rgba(16,185,129,0.15);
  color: #10b981;
  border: 1px solid rgba(16,185,129,0.3);
}

.status-badge.idle {
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.4);
  border: 1px solid rgba(255,255,255,0.1);
}

.status-badge.offline {
  background: rgba(255,255,255,0.03);
  color: rgba(255,255,255,0.2);
  border: 1px solid rgba(255,255,255,0.06);
}

.autonomy-badge {
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 20px;
  background: rgba(59,130,246,0.1);
  color: #3b82f6;
  border: 1px solid rgba(59,130,246,0.2);
  font-weight: 500;
}

.panel-task {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 16px;
}

.panel-task-label {
  display: block;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: rgba(255,255,255,0.3);
  margin-bottom: 5px;
}

.panel-task-text {
  font-size: 12px;
  color: rgba(255,255,255,0.65);
  line-height: 1.4;
}

.panel-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}

.metric-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-val {
  font-size: 16px;
  font-weight: 600;
  color: rgba(255,255,255,0.85);
}

.metric-label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: rgba(255,255,255,0.3);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.panel-workload {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.workload-label {
  font-size: 10px;
  color: rgba(255,255,255,0.35);
  min-width: 55px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.workload-bar {
  flex: 1;
  height: 4px;
  background: rgba(255,255,255,0.06);
  border-radius: 2px;
  overflow: hidden;
}

.workload-fill {
  height: 100%;
  background: var(--dept-color, #3b82f6);
  border-radius: 2px;
  box-shadow: 0 0 8px var(--dept-color, rgba(59,130,246,0.5));
  transition: width 0.5s ease;
}

.workload-pct {
  font-size: 10px;
  color: rgba(255,255,255,0.4);
  min-width: 30px;
  text-align: right;
}

.panel-view-link {
  display: block;
  text-align: center;
  padding: 10px;
  border: 1px solid rgba(59,130,246,0.25);
  border-radius: 6px;
  color: #3b82f6;
  font-size: 12px;
  text-decoration: none;
  transition: background 0.15s, border-color 0.15s;
}

.panel-view-link:hover {
  background: rgba(59,130,246,0.1);
  border-color: rgba(59,130,246,0.45);
}

.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: transform 0.35s cubic-bezier(0.16,1,0.3,1), opacity 0.25s ease;
}

.slide-panel-enter-from,
.slide-panel-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes glowPulseRing {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; box-shadow: 0 0 20px var(--dept-color, rgba(59,130,246,0.6)); }
}
</style>
