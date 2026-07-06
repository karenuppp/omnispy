<script setup lang="ts">
import { NMenu } from 'naive-ui'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const menuOptions = [
  { label: '监控面板', key: '/' },
  { label: '手动搜索', key: '/search' },
]

function handleUpdate(key: string) {
  router.push(key)
}
</script>

<template>
  <NMenu :value="route.path" :options="menuOptions" mode="horizontal" @update:value="handleUpdate" />
</template>
