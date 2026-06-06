<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getFieldConfig, putFieldConfig } from '@/api/fieldConfigurations'
import type { FieldConfigItem } from '@/types/fieldConfig'
import { useAuthStore } from '@/store/auth'

const FORM_KEY = 'WORK_ORDER'

// 工单表单可配置字段的中文名映射（title 始终必填、不可配置，故不在此列出）。
const FIELD_LABELS: Record<string, string> = {
  description: '描述',
  priority: '优先级',
  due_date: '截止日期',
  asset: '资产',
  location: '位置',
  assignee: '负责人',
  team: '团队',
  category: '分类',
  estimated_duration: '预计工时',
  estimated_start_date: '预计开始日期',
}

function fieldLabel(name: string): string {
  return FIELD_LABELS[name] ?? name
}

const auth = useAuthStore()
const canEdit = ref(auth.hasPermission('company.settings'))

const rows = ref<FieldConfigItem[]>([])
const loading = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await getFieldConfig(FORM_KEY)
    rows.value = data.map((d) => ({
      field_name: d.field_name,
      visible: d.visible,
      required: d.required,
    }))
  } catch {
    ElMessage.error('加载字段配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!canEdit.value) return
  saving.value = true
  try {
    const updated = await putFieldConfig(
      FORM_KEY,
      rows.value.map((r) => ({
        field_name: r.field_name,
        visible: r.visible,
        required: r.required,
      })),
    )
    rows.value = updated.map((d) => ({
      field_name: d.field_name,
      visible: d.visible,
      required: d.required,
    }))
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="work-order-fields-page">
    <h2 class="page-title">工单表单字段</h2>
    <el-card v-loading="loading">
      <p class="hint">配置「新建工单」表单中各字段的显示与必填规则（标题始终必填，不可配置）。</p>
      <el-table :data="rows" row-key="field_name" border style="width: 100%">
        <el-table-column label="字段" min-width="160">
          <template #default="{ row }">{{ fieldLabel(row.field_name) }}</template>
        </el-table-column>
        <el-table-column label="显示" width="120" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.visible" :disabled="!canEdit" />
          </template>
        </el-table-column>
        <el-table-column label="必填" width="120" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.required" :disabled="!canEdit || !row.visible" />
          </template>
        </el-table-column>
      </el-table>
      <div class="actions">
        <el-button
          v-if="canEdit"
          type="primary"
          :loading="saving"
          :disabled="loading"
          @click="handleSave"
        >
          保存
        </el-button>
        <span v-else class="readonly-hint">无 company.settings 权限，仅可查看</span>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.work-order-fields-page {
  max-width: 700px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #303133);
}
.hint {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.actions {
  margin-top: 16px;
}
.readonly-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
