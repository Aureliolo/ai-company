<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="logo">
        <span class="logo-icon">◈</span>
        <span class="logo-text">SynthOrg</span>
        <span class="logo-sub">/ Nexus Dynamics</span>
      </div>
    </div>
    <div class="topbar-right">
      <div class="status-item">
        <span class="status-dot active"></span>
        <span class="status-label">{{ activeCount }} active</span>
      </div>
      <div class="status-divider"></div>
      <div class="status-item">
        <span class="status-label mono">12 agents</span>
      </div>
      <div class="status-divider"></div>
      <div class="status-item">
        <span class="status-label mono">$42 today</span>
      </div>
      <div class="status-divider"></div>
      <div class="status-item connected">
        <span class="conn-dot"></span>
        <span class="status-label">Connected</span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { agents } from '../data/mockData'

const activeCount = computed(() => agents.filter(a => a.status === 'active').length)
</script>

<style scoped>
.topbar {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: rgba(8,8,15,0.95);
  backdrop-filter: blur(12px);
  position: relative;
  z-index: 100;
  flex-shrink: 0;
}

.topbar-left, .topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  color: #3b82f6;
  font-size: 18px;
  animation: glowPulse 3s ease-in-out infinite;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: rgba(255,255,255,0.92);
  letter-spacing: -0.3px;
}

.logo-sub {
  font-size: 12px;
  color: rgba(255,255,255,0.3);
  font-weight: 400;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.status-dot.active {
  box-shadow: 0 0 6px #10b981;
  animation: glowPulse 2s ease-in-out infinite;
}

.status-label {
  font-size: 12px;
  color: rgba(255,255,255,0.55);
}

.status-label.mono {
  font-family: 'JetBrains Mono', monospace;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.status-divider {
  width: 1px;
  height: 14px;
  background: rgba(255,255,255,0.1);
}

.connected {
  gap: 6px;
}

.conn-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 8px rgba(59,130,246,0.7);
  animation: glowPulse 2.5s ease-in-out infinite;
}

@keyframes glowPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
