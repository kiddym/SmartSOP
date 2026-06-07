<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { setAssignees, setTeams, attachProcedure, detachProcedure } from '@/api/workOrders'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listProceduresMini } from '@/api/procedures'
import { useAuthStore } from '@/store/auth'
import { formatDate } from '@/utils/format'
import type { WorkOrderRead, WorkOrderPriority } from '@/types/workOrder'
import type { UserRead, TeamRead } from '@/types/platform'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { ProcedureMini } from '@/types/maintenance'
import CustomFieldsSection from '@/components/CustomFieldsSection.vue'

const props = defineProps<{
  workOrder: WorkOrderRead
}>()

const emit = defineEmits<{
  changed: []
}>()

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const procedures = ref<ProcedureMini[]>([])

const assigneeIds = ref<string[]>([])
const teamIds = ref<string[]>([])
const selectedProcedure = ref('')
const savingAssign = ref(false)
const attaching = ref(false)

// ── priority label ─────────────────────────────────────────
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}

// ── mapping helpers ────────────────────────────────────────
function assetName(id: string | null): string {
  if (!id) return '—'
  const a = assetsMini.value.find((x) => x.id === id)
  return a ? a.name : '—'
}

function locationName(id: string | null): string {
  if (!id) return '—'
  const l = locationsMini.value.find((x) => x.id === id)
  return l ? l.name : '—'
}

function userName(id: string | null): string {
  if (!id) return '—'
  const u = users.value.find((x) => x.id === id)
  return u ? u.name : '—'
}

function priorityLabel(p: WorkOrderPriority): string {
  return PRIORITY_LABELS[p] ?? p
}

function procedureName(id: string | null): string {
  if (!id) return '—'
  const p = procedures.value.find((x) => x.id === id)
  return p ? p.name : '—'
}

// ── init ───────────────────────────────────────────────────
onMounted(async () => {
  await Promise.all([
    listUsers().then((v) => (users.value = v)),
    listTeams().then((v) => (teams.value = v)),
    listAssetsMini().then((v) => (assetsMini.value = v)),
    listLocationsMini().then((v) => (locationsMini.value = v)),
    listProceduresMini().then((v) => (procedures.value = v)),
  ])
})

watch(
  () => props.workOrder,
  (w) => {
    assigneeIds.value = [...w.assignee_ids]
    teamIds.value = [...w.team_ids]
  },
  { immediate: true },
)

// ── actions ────────────────────────────────────────────────
async function saveAssignment() {
  try {
    savingAssign.value = true
    await setAssignees(props.workOrder.id, { user_ids: assigneeIds.value })
    await setTeams(props.workOrder.id, { team_ids: teamIds.value })
    ElMessage.success('指派已保存')
    emit('changed')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    savingAssign.value = false
  }
}

async function doAttach() {
  if (!selectedProcedure.value) {
    ElMessage.warning('请选择 SOP')
    return
  }
  try {
    attaching.value = true
    await attachProcedure(props.workOrder.id, { procedure_id: selectedProcedure.value })
    ElMessage.success('已挂接')
    selectedProcedure.value = ''
    emit('changed')
  } catch {
    ElMessage.error('操作失败，请重试')
  } finally {
    attaching.value = false
  }
}

async function doDetach() {
  const result = await ElMessageBox.confirm('解绑 SOP 将清除执行步骤，确认？', '提示', {
    type: 'warning',
  }).catch(() => '__cancel__')
  if (result === '__cancel__') return
  try {
    await detachProcedure(props.workOrder.id)
    ElMessage.success('已解绑')
    emit('changed')
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

defineExpose({ assigneeIds, teamIds, selectedProcedure, saveAssignment, doAttach, doDetach })
</script>

<template>
  <div class="overview-tab">
    <!-- 基本信息 -->
    <el-descriptions :column="2" border class="info-section">
      <el-descriptions-item label="编号">{{ workOrder.custom_id }}</el-descriptions-item>
      <el-descriptions-item label="标题">{{ workOrder.title }}</el-descriptions-item>
      <el-descriptions-item label="描述" :span="2">
        {{ workOrder.description || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="优先级">
        {{ priorityLabel(workOrder.priority) }}
      </el-descriptions-item>
      <el-descriptions-item label="资产">{{ assetName(workOrder.asset_id) }}</el-descriptions-item>
      <el-descriptions-item label="位置">
        {{ locationName(workOrder.location_id) }}
      </el-descriptions-item>
      <el-descriptions-item label="负责人">
        {{ userName(workOrder.primary_user_id) }}
      </el-descriptions-item>
      <el-descriptions-item label="到期">
        {{ formatDate(workOrder.due_date) }}
      </el-descriptions-item>
      <el-descriptions-item label="完成时间">
        {{ formatDate(workOrder.completed_at) }}
      </el-descriptions-item>
    </el-descriptions>

    <!-- 指派 -->
    <div class="section">
      <h3 class="section-title">指派</h3>
      <div class="assign-row">
        <el-select
          v-model="assigneeIds"
          multiple
          filterable
          placeholder="请选择指派用户"
          style="width: 300px"
          :disabled="!auth.hasPermission('work_order.edit')"
        >
          <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
        </el-select>
        <el-select
          v-model="teamIds"
          multiple
          placeholder="请选择团队"
          style="width: 300px"
          :disabled="!auth.hasPermission('work_order.edit')"
        >
          <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-button
          v-if="auth.hasPermission('work_order.edit')"
          type="primary"
          :loading="savingAssign"
          @click="saveAssignment"
        >
          保存指派
        </el-button>
      </div>
    </div>

    <!-- SOP -->
    <div class="section">
      <h3 class="section-title">关联 SOP</h3>
      <template v-if="workOrder.procedure_id">
        <div class="assign-row">
          <span class="sop-attached">已挂接：{{ procedureName(workOrder.procedure_id) }}</span>
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            type="danger"
            plain
            @click="doDetach"
          >
            解绑
          </el-button>
        </div>
      </template>
      <template v-else>
        <div class="assign-row">
          <el-select
            v-model="selectedProcedure"
            placeholder="请选择 SOP"
            clearable
            filterable
            style="width: 300px"
          >
            <el-option v-for="pr in procedures" :key="pr.id" :label="pr.name" :value="pr.id" />
          </el-select>
          <el-button
            v-if="auth.hasPermission('work_order.edit')"
            type="primary"
            :loading="attaching"
            @click="doAttach"
          >
            挂接
          </el-button>
        </div>
      </template>
    </div>

    <!-- 自定义字段 -->
    <CustomFieldsSection
      entity-type="work_order"
      :model-value="(workOrder.custom_values ?? {})"
      readonly
    />
  </div>
</template>

<style scoped>
.overview-tab {
  padding: 16px 0;
}
.info-section {
  margin-bottom: 24px;
}
.section {
  margin-bottom: 24px;
}
.section-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}
.assign-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.sop-attached {
  color: var(--el-color-success);
  font-weight: 500;
}
</style>
