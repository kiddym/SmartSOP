<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWorkOrder, transitionWorkOrder } from '@/api/workOrders'
import { useAuthStore } from '@/store/auth'
import OverviewTab from '@/components/workorder/OverviewTab.vue'
import LaborCostTab from '@/components/workorder/LaborCostTab.vue'
import ActivityTab from '@/components/workorder/ActivityTab.vue'
import ExecutionTab from '@/components/workorder/ExecutionTab.vue'
import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'
import type { WorkOrderRead, WorkOrderStatus } from '@/types/workOrder'

// ── constants ──────────────────────────────────────────────
const WO_STATUS_LABELS: Record<WorkOrderStatus, string> = {
  OPEN: '待处理',
  IN_PROGRESS: '进行中',
  ON_HOLD: '挂起',
  COMPLETE: '已完成',
  CANCELED: '已取消',
}

const WO_STATUS_TAG: Record<WorkOrderStatus, string> = {
  OPEN: 'warning',
  IN_PROGRESS: 'primary',
  ON_HOLD: 'info',
  COMPLETE: 'success',
  CANCELED: 'danger',
}

const TRANSITIONS: Record<WorkOrderStatus, { to: WorkOrderStatus; label: string }[]> = {
  OPEN: [
    { to: 'IN_PROGRESS', label: '开始' },
    { to: 'CANCELED', label: '取消' },
  ],
  IN_PROGRESS: [
    { to: 'ON_HOLD', label: '挂起' },
    { to: 'COMPLETE', label: '完成' },
    { to: 'CANCELED', label: '取消' },
  ],
  ON_HOLD: [
    { to: 'IN_PROGRESS', label: '恢复' },
    { to: 'CANCELED', label: '取消' },
  ],
  COMPLETE: [{ to: 'IN_PROGRESS', label: '重开' }],
  CANCELED: [],
}

// ── state ──────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const woId = route.params.id as string
const wo = ref<WorkOrderRead | null>(null)
const loading = ref(false)
const activeTab = ref('overview')
const editVisible = ref(false)
const auth = useAuthStore()

// ── computed ───────────────────────────────────────────────
const transitions = computed(() => (wo.value ? TRANSITIONS[wo.value.status] : []))

// ── load ───────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    wo.value = await getWorkOrder(woId)
  } catch {
    ElMessage.error('加载工单失败，请重试')
    router.push('/maintenance/work-orders')
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── transition ─────────────────────────────────────────────
async function doTransition(t: { to: WorkOrderStatus; label: string }) {
  if (t.to === 'COMPLETE' || t.to === 'CANCELED') {
    const msg =
      t.to === 'COMPLETE' ? '确认标记完成？若有未完成步骤将被后端拒绝' : '确认取消该工单？'
    const result = await ElMessageBox.confirm(msg, '提示', { type: 'warning' }).catch(
      () => '__cancel__',
    )
    if (result === '__cancel__') return
  }
  try {
    wo.value = await transitionWorkOrder(woId, { to_status: t.to, note: '' })
    ElMessage.success('操作成功')
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

defineExpose({ doTransition, load, wo })
</script>

<template>
  <div v-loading="loading" class="page">
    <!-- 页头 -->
    <div class="page-header">
      <el-button link @click="router.push('/maintenance/work-orders')">← 返回</el-button>
      <div class="header-main">
        <span v-if="wo" class="page-title">{{ wo.custom_id }} {{ wo.title }}</span>
        <el-tag v-if="wo" :type="WO_STATUS_TAG[wo.status]" style="margin-left: 12px">
          {{ WO_STATUS_LABELS[wo.status] }}
        </el-tag>
      </div>
      <div v-if="auth.hasPermission('work_order.edit')" class="header-actions">
        <el-button v-for="t in transitions" :key="t.to" type="primary" @click="doTransition(t)">
          {{ t.label }}
        </el-button>
        <el-button @click="editVisible = true">编辑</el-button>
      </div>
    </div>

    <!-- tabs -->
    <el-tabs v-model="activeTab" style="margin-top: 16px">
      <el-tab-pane label="概览" name="overview">
        <OverviewTab v-if="wo" :work-order="wo" @changed="load" />
      </el-tab-pane>
      <el-tab-pane label="工时成本" name="labor-cost" lazy>
        <LaborCostTab :work-order-id="woId" />
      </el-tab-pane>
      <el-tab-pane label="活动" name="activity" lazy>
        <ActivityTab :work-order-id="woId" />
      </el-tab-pane>
      <el-tab-pane v-if="wo?.procedure_id" label="执行" name="execution" lazy>
        <ExecutionTab :work-order-id="woId" />
      </el-tab-pane>
    </el-tabs>

    <!-- 编辑对话框 -->
    <WorkOrderFormDialog v-model:visible="editVisible" mode="edit" :editing="wo" @saved="load" />
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  padding: 20px 24px;
}
.page-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}
.header-main {
  display: flex;
  align-items: center;
  flex: 1;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
