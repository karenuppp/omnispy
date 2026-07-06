<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NDataTable, NSpace, NTag, NIcon, NPopconfirm, NSpin, useMessage } from 'naive-ui'
import { Add as AddIcon, Refresh as RefreshIcon } from '@vicons/ionicons5'
import { listTasks, deleteTask, toggleTask, getStats, triggerRun } from '../api'
import type { Task, Stats } from '../types'

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
  await load()
}

async function handleToggle(id: number) {
  await toggleTask(id)
  await load()
}

async function handleRun(id: number) {
  await triggerRun(id)
  message.success('执行完成')
}

onMounted(load)

const columns = [
  { title: '名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'type',
    render(row: Task) {
      const map: Record<string, string> = { keyword: '关键词', user: '用户', mixed: '混合' }
      return h(NTag, { size: 'small', type: row.type === 'keyword' ? 'info' : row.type === 'user' ? 'success' : 'warning' },
        () => map[row.type] || row.type
      )
    },
  },
  { title: '关键词/用户', key: 'keywords', ellipsis: { tooltip: true } },
  { title: '调度', key: 'schedule' },
  {
    title: '状态',
    key: 'enabled',
    render(row: Task) {
      return h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' },
        () => row.enabled ? '启用' : '禁用'
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    render(row: Task) {
      return h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', onClick: () => router.push(`/tasks/${row.id}`) }, () => '详情'),
        h(NButton, { size: 'tiny', onClick: () => router.push(`/tasks/${row.id}/edit`) }, () => '编辑'),
        h(NButton, { size: 'tiny', onClick: () => handleToggle(row.id) }, () => row.enabled ? '禁用' : '启用'),
        h(NButton, { size: 'tiny', onClick: () => handleRun(row.id) }, () => '运行'),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          default: () => '确定删除此任务？',
          trigger: () => h(NButton, { size: 'tiny', type: 'error' }, () => '删除'),
        }),
      ])
    },
  },
]
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <h1 style="margin: 0;">Omnispy 监控面板</h1>
      <NSpace>
        <NButton @click="load" :loading="loading">
          <template #icon><NIcon><RefreshIcon /></NIcon></template>
          刷新
        </NButton>
        <NButton type="primary" @click="router.push('/tasks/new')">
          <template #icon><NIcon><AddIcon /></NIcon></template>
          新建任务
        </NButton>
      </NSpace>
    </div>

    <NSpace v-if="stats" style="margin-bottom: 16px;">
      <NCard size="small" style="min-width: 150px;">
        <template #header>总任务</template>
        {{ stats.total_tasks }}
      </NCard>
      <NCard size="small" style="min-width: 150px;">
        <template #header>已启用</template>
        {{ stats.enabled_tasks }}
      </NCard>
      <NCard size="small" style="min-width: 150px;">
        <template #header>今日执行</template>
        {{ stats.runs_today }}
      </NCard>
    </NSpace>

    <NCard>
      <template #header>定时任务列表</template>
      <NSpin :show="loading">
        <NDataTable :columns="columns" :data="tasks" :row-key="(r: Task) => r.id"
          :pagination="{ page: page, pageSize: 20, pageCount: Math.ceil(total / 20) }"
          @update:page="(p: number) => { page = p; load() }" />
      </NSpin>
    </NCard>
  </div>
</template>
