<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NForm, NFormItem, NInput, NSelect, NButton, NSpace, NCheckbox, NCard, useMessage,
} from 'naive-ui'
import { getTask, createTask, updateTask } from '../api'

const router = useRouter()
const route = useRoute()
const message = useMessage()
const isEdit = route.name === 'task-edit'
const taskId = Number(route.params.id)
const saving = ref(false)
const loading = ref(false)

const form = ref({
  name: '',
  type: 'keyword' as 'keyword' | 'user' | 'mixed',
  keywords: '',
  users: '',
  schedule: '0 9 * * *',
  enabled: 1,
})

const typeOptions = [
  { label: '关键词搜索', value: 'keyword' },
  { label: '用户时间线', value: 'user' },
  { label: '混合搜索', value: 'mixed' },
]

const schedulePresets = [
  { label: '每1小时', value: '0 * * * *' },
  { label: '每6小时', value: '0 */6 * * *' },
  { label: '每天 9:00', value: '0 9 * * *' },
  { label: '每天 21:00', value: '0 21 * * *' },
  { label: '每周一 9:00', value: '0 9 * * 1' },
]

onMounted(async () => {
  if (isEdit) {
    loading.value = true
    try {
      const res = await getTask(taskId)
      const t = res.data
      form.value = {
        name: t.name,
        type: t.type,
        keywords: t.keywords,
        users: t.users,
        schedule: t.schedule,
        enabled: t.enabled,
      }
    } finally {
      loading.value = false
    }
  }
})

async function handleSubmit() {
  saving.value = true
  try {
    if (isEdit) {
      await updateTask(taskId, form.value)
      message.success('任务已更新')
    } else {
      await createTask(form.value)
      message.success('任务已创建')
    }
    router.push('/')
  } catch (e: any) {
    message.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div style="max-width: 700px; margin: 0 auto; padding: 24px;">
    <NCard :title="isEdit ? '编辑任务' : '新建任务'" style="margin-bottom: 16px;">
      <NForm v-if="!loading" :model="form" label-placement="top" @submit.prevent="handleSubmit">
        <NFormItem label="任务名称" required>
          <NInput v-model:value="form.name" placeholder="例如：监控AI大模型动态" />
        </NFormItem>

        <NFormItem label="搜索类型" required>
          <NSelect v-model:value="form.type" :options="typeOptions" />
        </NFormItem>

        <NFormItem v-if="form.type === 'keyword' || form.type === 'mixed'" label="关键词（逗号分隔）">
          <NInput v-model:value="form.keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem v-if="form.type === 'user' || form.type === 'mixed'" label="用户名（逗号分隔，不带@）">
          <NInput v-model:value="form.users" placeholder="elonmusk,lexfridman" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem label="调度频率" required>
          <NSelect v-model:value="form.schedule" :options="schedulePresets" :allow-create="true"
            placeholder="选择或输入 cron 表达式" />
        </NFormItem>

        <NFormItem>
          <NCheckbox v-model:checked="form.enabled" :checked-value="1" :unchecked-value="0">
            创建后立即启用
          </NCheckbox>
        </NFormItem>

        <NSpace>
          <NButton type="primary" attr-type="submit" :loading="saving">
            {{ isEdit ? '保存修改' : '创建任务' }}
          </NButton>
          <NButton @click="router.push('/')">取消</NButton>
        </NSpace>
      </NForm>
    </NCard>
  </div>
</template>
