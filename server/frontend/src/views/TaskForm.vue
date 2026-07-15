<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NForm, NFormItem, NInput, NSelect, NButton, NSpace, NCheckbox, useMessage,
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
  <div class="form-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">{{ isEdit ? '编辑任务' : '新建任务' }}</h1>
        <p class="page-subtitle">{{ isEdit ? '修改定时任务的配置参数' : '创建一个新的社交媒体监控任务' }}</p>
      </div>
      <NButton quaternary @click="router.push('/')">← 返回</NButton>
    </div>

    <div class="form-card">
      <NForm v-if="!loading" :model="form" label-placement="top" @submit.prevent="handleSubmit">
        <div class="form-section">
          <h3 class="section-title">基本信息</h3>
          <NFormItem label="任务名称" required>
            <NInput v-model:value="form.name" placeholder="例如：监控AI大模型动态" clearable />
          </NFormItem>
          <NFormItem label="搜索类型" required>
            <NSelect v-model:value="form.type" :options="typeOptions" />
          </NFormItem>
        </div>

        <div class="form-section">
          <h3 class="section-title">搜索目标</h3>
          <NFormItem v-if="form.type === 'keyword' || form.type === 'mixed'" label="关键词（逗号分隔）">
            <NInput v-model:value="form.keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="3" clearable />
          </NFormItem>
          <NFormItem v-if="form.type === 'user' || form.type === 'mixed'" label="用户名（逗号分隔，不带@）">
            <NInput v-model:value="form.users" placeholder="elonmusk,lexfridman" type="textarea" :rows="3" clearable />
          </NFormItem>
        </div>

        <div class="form-section">
          <h3 class="section-title">调度设置</h3>
          <NFormItem label="调度频率" required>
            <NSelect v-model:value="form.schedule" :options="schedulePresets" :allow-create="true"
              placeholder="选择或输入 cron 表达式" filterable />
          </NFormItem>
          <NFormItem>
            <NCheckbox v-model:checked="form.enabled" :checked-value="1" :unchecked-value="0">
              创建后立即启用
            </NCheckbox>
          </NFormItem>
        </div>

        <div class="form-actions">
          <NSpace>
            <NButton type="primary" attr-type="submit" :loading="saving">
              {{ isEdit ? '保存修改' : '创建任务' }}
            </NButton>
            <NButton quaternary @click="router.push('/')">取消</NButton>
          </NSpace>
        </div>
      </NForm>
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
}

/* --- Sections --- */
.form-section {
  margin-bottom: 28px;
  padding-bottom: 28px;
  border-bottom: 1px solid #1f1f25;
}

.form-section:last-of-type {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #88889a;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 20px;
}

/* --- Action bar --- */
.form-actions {
  padding-top: 16px;
  border-top: 1px solid #1f1f25;
  margin-top: 28px;
}
</style>
