<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton, NDataTable, NSpace, NTag, NIcon, NPopconfirm, NSpin, useMessage,
} from 'naive-ui'
import {
  AddOutline as AddIcon, RefreshOutline as RefreshIcon, PlayOutline as RunIcon, TrashOutline as DeleteIcon,
} from '@vicons/ionicons5'
import { listTasks, deleteTask, toggleTask, getStats, triggerRun } from '../api'
import type { Task, Stats } from '../types'
import { formatDistance } from '../utils'

const router = useRouter()
const message = useMessage()
const tasks = ref<Task[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(true)
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const [tRes, sRes] = await Promise.all([
      listTasks(page.value, 20),
      getStats(),
    ])
    tasks.value = tRes.data.items
    total.value = tRes.data.total
    stats.value = sRes.data
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  await deleteTask(id)
  message.success('已删除')
  await load()
}

async function handleToggle(id: number) {
  await toggleTask(id)
  await load()
}

async function handleRun(id: number) {
  try {
    await triggerRun(id)
    message.success('执行完成')
  } catch {
    message.error('执行失败')
  }
}

onMounted(load)

const columns = [
  { title: '名称', key: 'name', ellipsis: { tooltip: true }, width: 160 },
  {
    title: '类型', key: 'type', width: 80,
    render(row: Task) {
      const map: Record<string, { label: string; color: string }> = {
        keyword: { label: '关键词', color: '#22d3a0' },
        user: { label: '用户', color: '#60a5fa' },
        mixed: { label: '混合', color: '#f59e0b' },
      }
      const info = map[row.type] || { label: row.type, color: '#88889a' }
      return h(NTag, {
        size: 'tiny',
        style: {
          border: `1px solid ${info.color}20`,
          background: `${info.color}10`,
          color: info.color,
        },
      }, () => info.label)
    },
  },
  { title: '关键词/用户', key: 'keywords', ellipsis: { tooltip: true }, width: 160 },
  { title: '调度', key: 'schedule', width: 90,
    render(row: Task) {
      return h('span', { style: { fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace", fontSize: '12px', color: '#88889a' } }, row.schedule)
    },
  },
  {
    title: '状态', key: 'enabled', width: 70,
    render(row: Task) {
      return h('span', {
        style: {
          display: 'inline-flex', alignItems: 'center', gap: '6px',
          color: row.enabled ? '#22d3a0' : '#5c5c6e', fontSize: '13px',
        },
      }, [
        h('span', { style: { width: '6px', height: '6px', borderRadius: '50%', background: row.enabled ? '#22d3a0' : '#5c5c6e', display: 'inline-block' } }),
        row.enabled ? '启用' : '禁用',
      ])
    },
  },
  {
    title: '', key: 'actions', width: 200,
    render(row: Task) {
      return h(NSpace, { size: 'small', justify: 'end', align: 'center' }, () => [
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => router.push(`/tasks/${row.id}`) }, () => '详情'),
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => router.push(`/tasks/${row.id}/edit`) }, () => '编辑'),
        h(NButton, { size: 'tiny', quaternary: true, onClick: () => handleToggle(row.id) }, () => row.enabled ? '禁用' : '启用'),
        h(NButton, {
          size: 'tiny', quaternary: true,
          style: { color: '#22d3a0', padding: '0 4px' },
          onClick: () => handleRun(row.id),
        }, { icon: () => h(NIcon, null, { default: () => h(RunIcon) }) }),
        h(NPopconfirm, {
          onPositiveClick: () => handleDelete(row.id),
          positiveButtonProps: { type: 'error' as const },
        }, {
          default: () => '确定删除此任务？',
          trigger: () => h(NButton, {
            size: 'tiny', quaternary: true,
            style: { color: '#5c5c6e', padding: '0 4px' },
          }, { icon: () => h(NIcon, null, { default: () => h(DeleteIcon) }) }),
        }),
      ])
    },
  },
]
</script>

<template>
  <div class="dashboard">
    <div class="page-header">
      <div>
        <h1 class="page-title">监控面板</h1>
        <p class="page-subtitle">管理社交媒体监控任务</p>
      </div>
      <NSpace>
        <NButton quaternary @click="load" :loading="loading">
          <template #icon><NIcon><RefreshIcon /></NIcon></template>
          刷新
        </NButton>
        <NButton type="primary" @click="router.push('/tasks/new')">
          <template #icon><NIcon><AddIcon /></NIcon></template>
          新建任务
        </NButton>
      </NSpace>
    </div>

    <div v-if="stats" class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">总任务</div>
        <div class="stat-value">{{ stats.total_tasks }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已启用</div>
        <div class="stat-value accent">{{ stats.enabled_tasks }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日执行</div>
        <div class="stat-value blue">{{ stats.runs_today }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">最近执行</div>
        <div class="stat-value muted">
          {{ stats.last_run_at ? formatDistance(stats.last_run_at) : '暂无' }}
        </div>
      </div>
    </div>

    <div class="table-container">
      <NSpin :show="loading">
        <NDataTable
          :columns="columns"
          :data="tasks"
          :row-key="(r: Task) => r.id"
          :pagination="{
            page: page,
            pageSize: 20,
            pageCount: Math.ceil(total / 20),
            simple: true,
          }"
          @update:page="(p: number) => { page = p; load() }"
          size="small"
          striped
          :bordered="false"
          :single-line="false"
        />
      </NSpin>
    </div>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 4px;
  color: #eaeaef;
  letter-spacing: -0.03em;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: #5c5c6e;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat-card {
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  padding: 16px 20px;
  transition: border-color 0.15s ease;
}

.stat-card:hover { border-color: #2a2a30; }

.stat-label {
  font-size: 11px;
  font-weight: 600;
  color: #5c5c6e;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #eaeaef;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.stat-value.accent { color: #22d3a0; }
.stat-value.blue { color: #60a5fa; }
.stat-value.muted {
  font-size: 13px;
  font-weight: 500;
  color: #88889a;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}

.table-container {
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  overflow: hidden;
}
</style>
