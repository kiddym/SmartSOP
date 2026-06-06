<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWorkOrder, transitionWorkOrder, downloadWorkOrderReport } from '@/api/workOrders'
import { WO_STATUS_LABELS, WO_STATUS_TAG } from '@/utils/workOrder'
import { useAuthStore } from '@/store/auth'
import OverviewTab from '@/components/workorder/OverviewTab.vue'
import LaborCostTab from '@/components/workorder/LaborCostTab.vue'
import ActivityTab from '@/components/workorder/ActivityTab.vue'
import ExecutionTab from '@/components/workorder/ExecutionTab.vue'
import PartsConsumptionTab from '@/components/workorder/PartsConsumptionTab.vue'
import WorkOrderFormDialog from '@/components/workorder/WorkOrderFormDialog.vue'
import type { WorkOrderRead, WorkOrderStatus } from '@/types/workOrder'

// ── constants ──────────────────────────────────────────────
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
  let signatureUrl: string | null = null
  // 完成且要求签名且尚无签名：弹出签名输入（url/文本，签名画布超范围）。
  if (t.to === 'COMPLETE' && wo.value?.required_signature && !wo.value?.signature_url) {
    const prompt = await ElMessageBox.prompt(
      '该工单完成前需要签名，请输入签名链接或标识',
      '完成签名',
      {
        confirmButtonText: '确认完成',
        cancelButtonText: '取消',
        inputPattern: /\S/,
        inputErrorMessage: '签名不能为空',
      },
    ).catch(() => null)
    if (!prompt) return
    signatureUrl = (prompt as { value: string }).value.trim()
  } else if (t.to === 'COMPLETE' || t.to === 'CANCELED') {
    const msg =
      t.to === 'COMPLETE' ? '确认标记完成？若有未完成步骤将被后端拒绝' : '确认取消该工单？'
    const result = await ElMessageBox.confirm(msg, '提示', { type: 'warning' }).catch(
      () => '__cancel__',
    )
    if (result === '__cancel__') return
  }
  try {
    wo.value = await transitionWorkOrder(woId, {
      to_status: t.to,
      note: '',
      ...(signatureUrl ? { signature_url: signatureUrl } : {}),
    })
    ElMessage.success('操作成功')
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── PDF 报告 ───────────────────────────────────────────────
const reportLoading = ref(false)
async function downloadReport() {
  if (!wo.value) return
  reportLoading.value = true
  try {
    await downloadWorkOrderReport(wo.value.id, wo.value.custom_id)
  } catch {
    ElMessage.error('生成 PDF 报告失败，请重试')
  } finally {
    reportLoading.value = false
  }
}

defineExpose({ doTransition, load, wo, downloadReport })
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
      <div class="header-actions">
        <el-button
          v-if="auth.hasPermission('work_order.view')"
          :loading="reportLoading"
          @click="downloadReport"
        >
          生成 PDF 报告
        </el-button>
        <template v-if="auth.hasPermission('work_order.edit')">
          <el-button v-for="t in transitions" :key="t.to" type="primary" @click="doTransition(t)">
            {{ t.label }}
          </el-button>
          <el-button @click="editVisible = true">编辑</el-button>
        </template>
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
      <el-tab-pane v-if="auth.hasPermission('part.view')" label="备件" name="parts" lazy>
        <PartsConsumptionTab :work-order-id="woId" />
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
