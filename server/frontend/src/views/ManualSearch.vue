<script setup lang="ts">
import { h, ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItem, NInput, NInputNumber, NSelect, NSpace, NSpin, useMessage } from 'naive-ui'

import { manualSearch } from '../api'

import type { Tweet } from '../types'

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
  { title: '时间', key: 'time', width: 180 },
  {
    title: '链接', key: 'url', width: 80,
    render(row: Tweet) {
      if (!row.url) return ''
      return h('a', { href: row.url, target: '_blank', rel: 'noopener' }, '打开')
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
  <div style="max-width: 1000px; margin: 0 auto; padding: 24px;">
    <h1>手动搜索</h1>

    <NCard style="margin-bottom: 16px;">
      <NForm label-placement="top" @submit.prevent="handleSearch">
        <NFormItem label="搜索类型">
          <NSelect v-model:value="queryType" :options="typeOptions" />
        </NFormItem>

        <NFormItem v-if="queryType === 'keyword'" label="关键词（逗号分隔）">
          <NInput v-model:value="keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem v-if="queryType === 'user'" label="用户名（逗号分隔，不带@）">
          <NInput v-model:value="users" placeholder="elonmusk,lexfridman" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem label="每个关键词/用户获取条数">
          <NInputNumber v-model:value="limit" :min="1" :max="100" style="width: 120px;" />
        </NFormItem>

        <NSpace>
          <NButton type="primary" attr-type="submit" :loading="searching">搜索</NButton>
        </NSpace>
      </NForm>
    </NCard>

    <NSpin :show="searching">
      <NCard v-if="searched" :title="`搜索结果 (${results.length} 条)`">
        <NDataTable v-if="results.length > 0" :columns="tweetColumns" :data="results" :row-key="(r: Tweet) => r.id" />
        <p v-else style="color: #888;">无结果</p>
      </NCard>
    </NSpin>
  </div>
</template>
