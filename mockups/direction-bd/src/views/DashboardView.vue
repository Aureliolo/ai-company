<template>
  <div class="dashboard-layout">
    <TopBar />
    <div class="dashboard-body">
      <Sidebar />
      <div class="dashboard-main">
        <ForceGraph />
        <AmbientTray />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import TopBar from '../components/TopBar.vue'
import Sidebar from '../components/Sidebar.vue'
import ForceGraph from '../components/ForceGraph.vue'
import AmbientTray from '../components/AmbientTray.vue'
</script>

<style scoped>
.dashboard-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #08080f;
  overflow: hidden;
}

.dashboard-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.dashboard-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
