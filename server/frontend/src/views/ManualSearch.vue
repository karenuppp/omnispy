<script setup lang="ts">
import { h, ref } from 'vue'
import {
  NButton, NDataTable, NForm, NFormItem, NInput, NInputNumber, NSelect, NSpace, NSpin, useMessage,
} from 'naive-ui'

import { manualSearch } from '../api'

import type { Tweet } from '../types'
import { formatTime } from '../utils'

const message = useMessage()

const queryType = ref<'keyword' | 'user'>('keyword')
const keywords = ref('')
const users = ref('')
const limit = ref(20)
const results = ref<Tweet[]>([])
const searching = ref(false)
const searched = ref(false)

const typeOptions = [
  { label: '关键词搜索', value: 'keyword' },
  { label: '用户时间线', value: 'user' },
]

const tweetColumns = [
  { title: '作者', key: 'author', width: 120 },
  { title: '内容', key: 'text', ellipsis: { tooltip: true } },
  {
    title: '时间', key: 'time', width: 170,
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

async function handleSearch() {
  searching.value = true
  searched.value = false
  try {
    const res = await manualSearch(queryType.value, keywords.value, users.value, limit.value)
    results.value = res.data.tweets
  } catch (e: any) {
    message.error('搜索失败')
  } finally {
    searching.value = false
    searched.value = true
  }
}
</script>

<template>
  <div class="form-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">手动搜索</h1>
        <p class="page-subtitle">临时搜索关键词或用户时间线</p>
      </div>
    </div>

    <div class="form-card">
      <NForm label-placement="top" @submit.prevent="handleSearch">
        <NFormItem label="搜索类型">
          <NSelect v-model:value="queryType" :options="typeOptions" />
        </NFormItem>

        <NFormItem v-if="queryType === 'keyword'" label="关键词（逗号分隔）">
          <NInput v-model:value="keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="3" clearable />
        </NFormItem>

        <NFormItem v-if="queryType === 'user'" label="用户名（逗号分隔，不带@）">
          <NInput v-model:value="users" placeholder="elonmusk,lexfridman" type="textarea" :rows="3" clearable />
        </NFormItem>

        <div class="form-actions">
          <NFormItem label="每项获取条数" class="limit-field">
            <NInputNumber v-model:value="limit" :min="1" :max="100" style="width: 120px;" />
          </NFormItem>
          <NButton type="primary" attr-type="submit" :loading="searching" class="submit-btn">
            搜索
          </NButton>
        </div>
      </NForm>
    </div>

    <div v-if="searched" class="results-section">
      <div class="results-header">
        <h3 class="results-title">搜索结果</h3>
        <span class="results-count">{{ results.length }} 条</span>
      </div>

      <NSpin :show="searching">
        <div v-if="results.length > 0" class="results-card">
          <NDataTable
            :columns="tweetColumns"
            :data="results"
            :row-key="(r: Tweet) => r.id"
            size="small"
            :bordered="false"
            :single-line="false"
          />
        </div>
        <div v-else class="empty-state">
          <p>无结果</p>
        </div>
      </NSpin>
    </div>
  </div>
</template>

<style scoped>
/* --- Layout --- */
.form-page { max-width: 680px; }

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

/* --- Card --- */
.form-card {
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  padding: 32px;
  margin-bottom: 24px;
}

/* --- Actions row: limit field + search button --- */
.form-actions {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}

.limit-field {
  flex: none;
  margin-bottom: 0;
}

.submit-btn {
  margin-left: auto;
  height: 34px;
}

/* --- Results --- */
.results-section {
  margin-top: 4px;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.results-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #eaeaef;
}

.results-count {
  font-size: 12px;
  color: #5c5c6e;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.results-card {
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  overflow: hidden;
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
  background: #131317;
  border: 1px solid #1f1f25;
  border-radius: 10px;
  color: #5c5c6e;
  font-size: 14px;
}
</style>
