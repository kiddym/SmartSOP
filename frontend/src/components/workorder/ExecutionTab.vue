<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getExecution } from '@/api/workOrders'
import { listUsers } from '@/api/users'
import type { ExecutionView } from '@/types/workOrder'
import type { UserRead } from '@/types/platform'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ workOrderId: string }>()

const exec = ref<ExecutionView | null>(null)
const users = ref<UserRead[]>([])
const loading = ref(false)

function userName(id: string | null): string {
  if (!id) return '—'
  const found = users.value.find((u) => u.id === id)
  return found ? found.name : '—'
}

onMounted(async () => {
  loading.value = true
  try {
    const [u, e] = await Promise.all([listUsers(), getExecution(props.workOrderId)])
    users.value = u
    exec.value = e
  } catch {
    ElMessage.error('加载执行视图失败，请重试')
  } finally {
    loading.value = false
  }
})

defineExpose({ exec })
</script>

<template>
  <div v-loading="loading" class="execution-tab">
    <template v-if="exec?.procedure">
      <div class="procedure-header">
        <span class="procedure-code">{{ exec.procedure.code }}</span>
        <span class="procedure-name">{{ exec.procedure.name }}</span>
        <el-tag size="small" type="info">v{{ exec.procedure.version }}</el-tag>
      </div>
    </template>

    <el-table :data="exec?.steps ?? []" style="width: 100%" class="steps-table">
      <el-table-column label="节点" prop="node_code" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_done ? 'success' : 'info'">
            {{ row.is_done ? '已完成' : '未完成' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="完成人" width="120">
        <template #default="{ row }">
          {{ userName(row.done_by_user_id) }}
        </template>
      </el-table-column>
      <el-table-column label="完成时间" width="160">
        <template #default="{ row }">
          {{ formatDateTime(row.done_at) }}
        </template>
      </el-table-column>
      <el-table-column label="备注" prop="notes" min-width="120" />
    </el-table>
  </div>
</template>

<style scoped>
.execution-tab {
  padding: 16px 0;
}
.procedure-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 15px;
}
.procedure-code {
  color: var(--el-text-color-secondary);
}
.procedure-name {
  font-weight: 600;
}
.steps-table {
  margin-top: 8px;
}
</style>
