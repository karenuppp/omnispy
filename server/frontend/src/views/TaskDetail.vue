<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NCard, NDataTable, NTag, NButton, NSpace, NSpin, NTabs, NTabPane, useMessage,
} from 'naive-ui'
import { getTask, listRuns, listTaskTweets, triggerRun } from '../api'
import type { Task, TaskRun, Tweet } from '../types'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const taskId = Number(route.params.id)
const task = ref<Task | null>(null)
const runs = ref<TaskRun[]>([])
const tweets = ref<Tweet[]>([])
const loading = ref(true)

const runColumns = [
  { title: '开始时间', key: 'started_at', width: 180 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row: TaskRun) {
      const map: Record<string, string> = { running: '运行中', success: '成功', failed: '失败' }
      return h(NTag, { size: 'small', type: row.status === 'success' ? 'success' : row.status === 'failed' ? 'error' : 'warning' },
        () => map[row.status] || row.status
      )
    },
  },
  { title: '错误信息', key: 'error_msg', ellipsis: { tooltip: true } },
]

const tweetColumns = [
  { title: '作者', key: 'author', width: 120 },
  { title: '内容', key: 'text', ellipsis: { tooltip: true } },
  { title: '时间', key: 'time', width: 180 },
  {
    title: '链接',
    key: 'url',
    width: 80,
    render(row: Tweet) {
      if (!row.url) return ''
      return h('a', { href: row.url, target: '_blank', rel: 'noopener' }, '打开')
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
  await triggerRun(taskId)
  message.success('执行完成')
  await load()
}

onMounted(load)
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 24px;">
    <NSpace style="margin-bottom: 16px;">
      <NButton @click="router.push('/')">← 返回</NButton>
      <NButton v-if="task" @click="router.push(`/tasks/${task.id}/edit`)">编辑</NButton>
      <NButton type="primary" @click="handleRun">立即执行</NButton>
    </NSpace>

    <NSpin :show="loading">
      <NCard v-if="task" :title="task.name" style="margin-bottom: 16px;">
        <NSpace>
          <NTag :type="task.type === 'keyword' ? 'info' : task.type === 'user' ? 'success' : 'warning'">
            {{ task.type === 'keyword' ? '关键词' : task.type === 'user' ? '用户' : '混合' }}
          </NTag>
          <NTag v-if="task.keywords">关键词: {{ task.keywords }}</NTag>
          <NTag v-if="task.users">用户: {{ task.users }}</NTag>
          <NTag>调度: {{ task.schedule }}</NTag>
          <NTag :type="task.enabled ? 'success' : 'default'">
            {{ task.enabled ? '已启用' : '已禁用' }}
          </NTag>
        </NSpace>
      </NCard>

      <NTabs type="line">
        <NTabPane tab="执行记录" name="runs">
          <NDataTable :columns="runColumns" :data="runs" :row-key="(r: TaskRun) => r.id" />
        </NTabPane>
        <NTabPane tab="最新推文" name="tweets">
          <NDataTable :columns="tweetColumns" :data="tweets" :row-key="(r: Tweet) => r.id" />
        </NTabPane>
      </NTabs>
    </NSpin>
  </div>
</template>
