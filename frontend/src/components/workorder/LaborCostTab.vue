<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listLabor,
  deleteLabor,
  stopTimer,
  startTimer,
  listAdditionalCosts,
  deleteAdditionalCost,
  getCostSummary,
} from '@/api/workOrders'
import { listUsers } from '@/api/users'
import { listCostCategories } from '@/api/costCategories'
import { useAuthStore } from '@/store/auth'
import LaborDialog from '@/components/workorder/LaborDialog.vue'
import AdditionalCostDialog from '@/components/workorder/AdditionalCostDialog.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import type {
  LaborRead,
  AdditionalCostRead,
  CostSummaryRead,
  CostCategoryRead,
} from '@/types/workOrder'
import type { UserRead } from '@/types/platform'

const props = defineProps<{ workOrderId: string }>()

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const labor = ref<LaborRead[]>([])
const costs = ref<AdditionalCostRead[]>([])
const summary = ref<CostSummaryRead | null>(null)
const users = ref<UserRead[]>([])
const costCategories = ref<CostCategoryRead[]>([])

const laborDialogVisible = ref(false)
const editingLabor = ref<LaborRead | null>(null)
const costDialogVisible = ref(false)
const editingCost = ref<AdditionalCostRead | null>(null)

// ── helpers ────────────────────────────────────────────────
function userName(id: string | null): string {
  if (!id) return '—'
  const u = users.value.find((x) => x.id === id)
  return u ? u.name : '—'
}

function costCategoryName(id: string | null): string {
  if (!id) return '—'
  const c = costCategories.value.find((x) => x.id === id)
  return c ? c.name : '—'
}

function durationText(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

// ── data loading ───────────────────────────────────────────
async function reloadAll() {
  const p = props.workOrderId
  const [l, c, s] = await Promise.all([listLabor(p), listAdditionalCosts(p), getCostSummary(p)])
  labor.value = l
  costs.value = c
  summary.value = s
}

onMounted(async () => {
  loading.value = true
  try {
    const [u, cc] = await Promise.all([listUsers(), listCostCategories(), reloadAll()])
    users.value = u
    costCategories.value = cc
  } finally {
    loading.value = false
  }
})

// ── labor actions ──────────────────────────────────────────
async function removeLabor(row: LaborRead) {
  try {
    await ElMessageBox.confirm('确认删除该工时？', '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteLabor(props.workOrderId, row.id)
    await reloadAll()
  } catch {
    // confirm reject or error — silent
  }
}

async function handleStopTimer(row: LaborRead) {
  try {
    await stopTimer(props.workOrderId, row.id)
    await reloadAll()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

async function handleStartTimer() {
  try {
    await startTimer(props.workOrderId)
    await reloadAll()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── cost actions ───────────────────────────────────────────
async function removeCost(row: AdditionalCostRead) {
  try {
    await ElMessageBox.confirm('确认删除该成本？', '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteAdditionalCost(props.workOrderId, row.id)
    await reloadAll()
  } catch {
    // confirm reject or error — silent
  }
}

function openCreateLabor() {
  editingLabor.value = null
  laborDialogVisible.value = true
}
function openEditLabor(row: LaborRead) {
  editingLabor.value = row
  laborDialogVisible.value = true
}
function openCreateCost() {
  editingCost.value = null
  costDialogVisible.value = true
}
function openEditCost(row: AdditionalCostRead) {
  editingCost.value = row
  costDialogVisible.value = true
}

defineExpose({ removeLabor, removeCost, reloadAll, handleStartTimer, handleStopTimer })
</script>

<template>
  <div v-loading="loading">
    <!-- 成本汇总 -->
    <div class="kpi-row">
      <KpiCard label="工时合计" :value="summary?.labor_total ?? '—'" unit="元" />
      <KpiCard label="额外成本合计" :value="summary?.additional_total ?? '—'" unit="元" />
      <KpiCard label="备件合计" :value="summary?.parts_total ?? '—'" unit="元" />
      <KpiCard label="总计" :value="summary?.total ?? '—'" unit="元" />
    </div>

    <!-- 工时区 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">工时记录</span>
        <div class="section-actions">
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            type="primary"
            size="small"
            @click="openCreateLabor"
          >
            新增工时
          </el-button>
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            size="small"
            @click="handleStartTimer"
          >
            开始计时
          </el-button>
        </div>
      </div>
      <el-table :data="labor" border style="width: 100%; margin-top: 8px">
        <el-table-column label="执行人" min-width="120">
          <template #default="{ row }">{{ userName(row.user_id) }}</template>
        </el-table-column>
        <el-table-column label="时长" min-width="100">
          <template #default="{ row }">{{
            durationText(row.running ? (row.running_elapsed_seconds ?? 0) : row.duration_seconds)
          }}</template>
        </el-table-column>
        <el-table-column prop="hourly_rate" label="费率（元/时）" min-width="120" />
        <el-table-column prop="cost" label="成本（元）" min-width="110" />
        <el-table-column label="状态" min-width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.running" type="success">计时中</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="140" />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="auth.hasPermission('work_order.edit')"
              link
              type="primary"
              @click="openEditLabor(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="row.running && auth.hasPermission('work_order.edit')"
              link
              type="warning"
              @click="handleStopTimer(row)"
            >
              停止
            </el-button>
            <el-button
              v-if="auth.hasPermission('work_order.edit')"
              link
              type="danger"
              @click="removeLabor(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 额外成本区 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">额外成本</span>
        <div class="section-actions">
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            type="primary"
            size="small"
            @click="openCreateCost"
          >
            新增成本
          </el-button>
        </div>
      </div>
      <el-table :data="costs" border style="width: 100%; margin-top: 8px">
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="amount" label="金额（元）" min-width="120" />
        <el-table-column label="类别" min-width="120">
          <template #default="{ row }">{{ costCategoryName(row.cost_category_id) }}</template>
        </el-table-column>
        <el-table-column label="备注" min-width="160">
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="auth.hasPermission('work_order.edit')"
              link
              type="primary"
              @click="openEditCost(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="auth.hasPermission('work_order.edit')"
              link
              type="danger"
              @click="removeCost(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 对话框 -->
    <LaborDialog
      v-model:visible="laborDialogVisible"
      :work-order-id="workOrderId"
      :editing="editingLabor"
      @saved="reloadAll"
    />
    <AdditionalCostDialog
      v-model:visible="costDialogVisible"
      :work-order-id="workOrderId"
      :editing="editingCost"
      @saved="reloadAll"
    />
  </div>
</template>

<style scoped>
.kpi-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 24px;
}
.kpi-row > * {
  flex: 1;
  min-width: 160px;
}
.section {
  margin-bottom: 32px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.section-actions {
  display: flex;
  gap: 8px;
}
</style>
