<template>
  <div class="ambient-tray" :class="{ collapsed }">
    <div class="tray-header" @click="collapsed = !collapsed">
      <div class="tray-title">
        <span class="tray-dot"></span>
        <span class="tray-label">Activity Feed</span>
        <span class="tray-count mono">{{ recentCount }} events in last 5 min</span>
      </div>
      <button class="tray-toggle">{{ collapsed ? '▲' : '▼' }}</button>
    </div>
    <div class="tray-content" v-show="!collapsed">
      <div class="event-list">
        <transition-group name="event" tag="div" class="event-items">
          <div
            v-for="event in activityFeed"
            :key="event.id"
            class="event-item"
            :class="event.type"
          >
            <span class="event-time mono">{{ event.time }}</span>
            <span class="event-icon">{{ eventIcon(event.type) }}</span>
            <span class="event-from">{{ event.from }}</span>
            <span class="event-arrow">→</span>
            <span class="event-to">{{ event.to }}</span>
            <span class="event-desc">{{ event.description }}</span>
          </div>
        </transition-group>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { activityFeed } from '../data/mockData'

const collapsed = ref(false)

const recentCount = computed(() =>
  activityFeed.filter(e => {
    const mins = parseInt(e.time)
    return !isNaN(mins) && mins <= 5
  }).length
)

function eventIcon(type: string): string {
  const icons: Record<string, string> = {
    message: '◌',
    task: '◆',
    approval: '◉',
    meeting: '◎',
  }
  return icons[type] || '◌'
}
</script>

<style scoped>
.ambient-tray {
  height: 160px;
  background: rgba(8,8,20,0.85);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(255,255,255,0.07);
  flex-shrink: 0;
  transition: height 0.3s cubic-bezier(0.16,1,0.3,1);
  display: flex;
  flex-direction: column;
  position: relative;
}

.ambient-tray::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(59,130,246,0.3), rgba(139,92,246,0.3), transparent);
}

.ambient-tray.collapsed {
  height: 40px;
}

.tray-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 40px;
  cursor: pointer;
  flex-shrink: 0;
}

.tray-header:hover {
  background: rgba(255,255,255,0.02);
}

.tray-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tray-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
  animation: glowPulse 2s ease-in-out infinite;
}

.tray-label {
  font-size: 11px;
  font-weight: 500;
  color: rgba(255,255,255,0.5);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.tray-count {
  font-size: 11px;
  color: rgba(255,255,255,0.25);
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.tray-toggle {
  background: transparent;
  border: none;
  color: rgba(255,255,255,0.25);
  cursor: pointer;
  font-size: 10px;
  padding: 4px 8px;
  transition: color 0.15s;
}

.tray-toggle:hover {
  color: rgba(255,255,255,0.5);
}

.tray-content {
  flex: 1;
  overflow: hidden;
}

.event-list {
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 0 20px 12px;
}

.event-items {
  display: flex;
  gap: 10px;
  height: 100%;
  align-items: center;
}

.event-item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}

.event-item:hover {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.12);
}

.event-item.approval {
  border-color: rgba(245,158,11,0.2);
}

.event-item.task {
  border-color: rgba(59,130,246,0.2);
}

.event-time {
  font-size: 10px;
  color: rgba(255,255,255,0.25);
  min-width: 36px;
}

.event-icon {
  font-size: 11px;
  color: rgba(255,255,255,0.3);
}

.event-from {
  font-size: 12px;
  color: #3b82f6;
  font-weight: 500;
}

.event-arrow {
  font-size: 11px;
  color: rgba(255,255,255,0.2);
}

.event-to {
  font-size: 12px;
  color: #8b5cf6;
  font-weight: 500;
}

.event-desc {
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-enter-active,
.event-leave-active {
  transition: all 0.3s ease;
}
.event-enter-from,
.event-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@keyframes glowPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
