<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { PulseOutline as DashboardIcon, SearchOutline as SearchIcon } from '@vicons/ionicons5'

const router = useRouter()
const route = useRoute()

const navItems = [
  { label: '监控面板', path: '/', icon: DashboardIcon },
  { label: '手动搜索', path: '/search', icon: SearchIcon },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-logo" @click="router.push('/')">
      <span class="logo-icon">◆</span>
      <span class="logo-text">Omnispy</span>
    </div>

    <nav class="sidebar-nav">
      <div
        v-for="item in navItems"
        :key="item.path"
        :class="['nav-item', { active: isActive(item.path) }]"
        @click="router.push(item.path)"
      >
        <component :is="item.icon" class="nav-icon" />
        <span>{{ item.label }}</span>
      </div>
    </nav>

    <div class="sidebar-footer">
      <span class="version">v0.1</span>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  min-height: 100vh;
  background: #08080c;
  border-right: 1px solid #1a1a20;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
}

.sidebar-logo {
  padding: 20px 20px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.logo-icon {
  font-size: 20px;
  color: #22d3a0;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: #eaeaef;
  letter-spacing: -0.02em;
}

.sidebar-nav {
  flex: 1;
  padding: 0 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #88889a;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
}

.nav-item:hover {
  color: #eaeaef;
  background: rgba(255, 255, 255, 0.04);
}

.nav-item.active {
  color: #eaeaef;
  background: rgba(34, 211, 160, 0.08);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 0 3px 3px 0;
  background: #22d3a0;
}

.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid #1a1a20;
}

.version {
  font-size: 12px;
  color: #5c5c6e;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}
</style>
