<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton, NDataTable, NTag, NSpace, NSpin, NTabs, NTabPane, useMessage,
} from 'naive-ui'
import { getTask, listRuns, listTaskTweets, triggerRun } from '../api'
import type { Task, TaskRun, Tweet } from '../types'
import { formatTime, formatDistance } from '../utils'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const taskId = Number(route.params.id)
const task = ref<Task | null>(null)
const runs = ref<TaskRun[]>([])
const tweets = ref<Tweet[]>([])
const loading = ref(true)

const runColumns = [
  {
    title: '执行时间', key: 'started_at', width: 180,
    render(row: TaskRun) {
      return h('span', { style: { fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: '12px', color: '#88889a' } }, formatTime(row.started_at))
    },
  },
  {
    title: '状态', key: 'status', width: 100,
    render(row: TaskRun) {
      const map: Record<string, { label: string; type: string; color: string }> = {
        running: { label: '运行中', type: 'warning', color: '#f59e0b' },
        success: { label: '成功', type: 'success', color: '#22d3a0' },
        failed: { label: '失败', type: 'error', color: '#f43f5e' },
      }
      const info = map[row.status] || { label: row.status, type: 'default', color: '#88889a' }
      return h(NTag, {
        size: 'small',
        style: { border: `1px solid ${info.color}20`, background: `${info.color}10`, color: info.color },
      }, () => info.label)
    },
  },
  {
    title: '耗时', key: 'started_at', width: 100,
    render(row: TaskRun) {
      if (!row.finished_at) return '-'
      const start = new Date(row.started_at).getTime()
      const end = new Date(row.finished_at).getTime()
      const sec = ((end - start) / 1000).toFixed(1)
      return h('span', { style: { fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: '12px', color: '#88889a' } }, `${sec}s`)
    },
  },
  { title: '错误信息', key: 'error_msg', ellipsis: { tooltip: true } },
]

const tweetColumns = [
  { title: '作者', key: 'author', width: 120 },
  { title: '内容', key: 'text', ellipsis: { tooltip: true } },
  {
    title: '时间', key: 'time', width: 160,
    render(row: Tweet) {
      return h('span', { style: { fontFamily: "'SF Mono', 'Fira Code', monospace", fontSize: '12px', color: '#88889a' } }, formatTime(row.time))
    },
  },
  {
    title: '链接', key: 'url', width: 60,
    render(row: Tweet) {
      if (!row.url) return ''
      return h('a', {
        href: row.url, target: '_blank', rel: 'noopener',
        style: { color: '#22d3a0', textDecoration: 'none', fontSize: '13px' },
      }, '打开')
    },
  },
]

async function load() {
  loading.value = true
  try {
    const [tRes, runsRes, twRes] = await Promise.all([
      getTask(taskId),
      listRuns(taskId, 1, 20),
      listTaskTweets(taskId, 1, 50),
    ])
    task.value = tRes.data
    runs.value = runsRes.data.items
    tweets.value = twRes.data.items
  } finally {
    loading.value = false
  }
}

async function handleRun() {
  try {
    await triggerRun(taskId)
    message.success('执行完成')
    await load()
  } catch {
    message.error('执行失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="detail-page">
    <div class="page-header">
      <div>
        <NSpace align="center" size="small">
          <NButton quaternary size="small" @click="router.push('/')">← 返回</NButton>
          <h1 class="page-title" v-if="task">{{ task.name }}</h1>
        </NSpace>
      </div>
      <NSpace>
        <NButton v-if="task" quaternary @click="router.push(`/tasks/${task.id}/edit`)">编辑</NButton>
        <NButton type="primary" size="small" @click="handleRun">立即执行</NButton>
      </NSpace>
    </div>

    <NSpin :show="loading">
      <div v-if="task" class="task-meta">
        <span :class="['meta-tag', `type-${task.type}`]">
          {{ task.type === 'keyword' ? '关键词' : task.type === 'user' ? '用户' : '混合' }}
        </span>
        <span v-if="task.keywords" class="meta-tag">
          关键词: {{ task.keywords }}
        </span>
        <span v-if="task.users" class="meta-tag">
          用户: {{ task.users }}
        </span>
        <span class="meta-tag mono">
          {{ task.schedule }}
        </span>
        <span :class="['meta-tag', task.enabled ? 'status-on' : 'status-off']">
          <span class="dot" />
          {{ task.enabled ? '已启用' : '已禁用' }}
        </span>
        <span class="meta-tag muted">
          创建于 {{ formatTime(task.created_at) }}
        </span>
      </div>

      <div class="tabs-card">
        <NTabs type="line">
          <NTabPane tab="执行记录" name="runs">
            <NDataTable
              :columns="runColumns"
              :data="runs"
              :row-key="(r: TaskRun) => r.id"
              size="small"
              :bordered="false"
              :single-line="false"
            />
          </NTabPane>
          <NTabPane tab="最新推文" name="tweets">
            <NDataTable
              :columns="tweetColumns"
              :data="tweets"
              :row-key="(r: Tweet) => r.id"
              size="small"
              :bordered="false"
              :single-line="false"
            />
          </NTabPane>
        </NTabs>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.detail-page { max-width: 1100px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  margin: 0;
  color: #eaeaef;
  letter-spacing: -0.03em;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
}

.meta-tag {
  font-size: 12px;
  font-weight: 500;
  color: #eaeaef;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 10px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.meta-tag.mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #88889a;
}

.meta-tag.muted { color: #5c5c6e; }

.meta-tag.type-keyword { background: rgba(34, 211, 160, 0.1); color: #22d3a0; }
.meta-tag.type-user { background: rgba(96, 165, 250, 0.1); color: #60a5fa; }
.meta-tag.type-mixed { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }

.meta-tag.status-on { color: #22d3a0; }
.meta-tag.status-off { color: #5c5c6e; }

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
}

.tabs-card {
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  padding: 16px 20px;
}
</style>
