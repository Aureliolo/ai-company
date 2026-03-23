<template>
  <nav class="sidebar" :class="{ expanded }">
    <div class="sidebar-inner">
      <div
        v-for="item in navItems"
        :key="item.path"
        class="nav-item"
        :class="{ active: currentPath === item.path }"
        @click="navigate(item.path)"
        @mouseenter="hoveredItem = item.id"
        @mouseleave="hoveredItem = null"
      >
        <span class="nav-icon" v-html="item.icon"></span>
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
      </div>
    </div>
    <button class="sidebar-toggle" @click="expanded = !expanded" :title="expanded ? 'Collapse' : 'Expand'">
      <span>{{ expanded ? '‹' : '›' }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const expanded = ref(false)
const hoveredItem = ref<string | null>(null)

const currentPath = computed(() => route.path)

const navItems = [
  { id: 'overview', path: '/', icon: '⬡', label: 'Overview', badge: null },
  { id: 'org', path: '/org', icon: '◎', label: 'Org Chart', badge: null },
  { id: 'tasks', path: '#', icon: '⊞', label: 'Tasks', badge: '5' },
  { id: 'people', path: '/agent', icon: '◈', label: 'People', badge: null },
  { id: 'money', path: '#', icon: '⊕', label: 'Budget', badge: null },
  { id: 'approvals', path: '#', icon: '◻', label: 'Approvals', badge: '2' },
  { id: 'comms', path: '#', icon: '⊂', label: 'Comms', badge: null },
  { id: 'meetings', path: '#', icon: '○', label: 'Meetings', badge: null },
  { id: 'providers', path: '#', icon: '◇', label: 'Providers', badge: null },
  { id: 'settings', path: '#', icon: '⊛', label: 'Settings', badge: null },
]

function navigate(path: string) {
  if (path !== '#') {
    router.push(path)
  }
}
</script>

<style scoped>
.sidebar {
  width: 60px;
  height: 100%;
  background: rgba(8,8,15,0.95);
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.25s cubic-bezier(0.16,1,0.3,1);
  overflow: hidden;
  position: relative;
  z-index: 50;
}

.sidebar.expanded {
  width: 200px;
}

.sidebar-inner {
  flex: 1;
  padding: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 18px;
  cursor: pointer;
  border-radius: 0;
  transition: background 0.15s ease;
  position: relative;
  white-space: nowrap;
  min-width: 0;
}

.nav-item:hover {
  background: rgba(59,130,246,0.08);
}

.nav-item:hover .nav-icon {
  color: #3b82f6;
  text-shadow: 0 0 12px rgba(59,130,246,0.8);
}

.nav-item.active {
  background: rgba(59,130,246,0.12);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: #3b82f6;
  border-radius: 0 2px 2px 0;
  box-shadow: 0 0 8px rgba(59,130,246,0.6);
}

.nav-item.active .nav-icon {
  color: #3b82f6;
  text-shadow: 0 0 12px rgba(59,130,246,0.8);
}

.nav-icon {
  font-size: 18px;
  color: rgba(255,255,255,0.35);
  transition: color 0.15s, text-shadow 0.15s;
  min-width: 24px;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-label {
  font-size: 13px;
  color: rgba(255,255,255,0.6);
  opacity: 0;
  transition: opacity 0.2s ease;
  flex: 1;
}

.sidebar.expanded .nav-label {
  opacity: 1;
}

.nav-badge {
  font-size: 10px;
  background: rgba(59,130,246,0.25);
  color: #3b82f6;
  border-radius: 10px;
  padding: 1px 6px;
  font-family: 'JetBrains Mono', monospace;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.sidebar.expanded .nav-badge {
  opacity: 1;
}

.sidebar-toggle {
  width: 100%;
  height: 36px;
  background: transparent;
  border: none;
  border-top: 1px solid rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.25);
  cursor: pointer;
  font-size: 16px;
  transition: color 0.15s, background 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  color: rgba(255,255,255,0.6);
  background: rgba(255,255,255,0.04);
}
</style>
