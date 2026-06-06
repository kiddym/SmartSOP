<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listWorkflows, createWorkflow, updateWorkflow, deleteWorkflow } from '@/api/workflows'
import { listWorkOrderCategories } from '@/api/workOrderCategories'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import type {
  WorkflowRead,
  WorkflowCreate,
  WorkflowUpdate,
  WorkflowTrigger,
  WorkflowCondition,
  WorkflowAction,
  ConditionField,
  ConditionOp,
  ActionType,
} from '@/types/workflow'
import type { WorkOrderCategoryRead } from '@/types/workOrder'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── 静态枚举与中文标签 ──────────────────────────────────────
const TRIGGER_LABELS: Record<WorkflowTrigger, string> = {
  WORK_ORDER_CREATED: '工单创建时',
  WORK_ORDER_STATUS_CHANGED: '工单状态变更时',
}
const FIELD_LABELS: Record<ConditionField, string> = {
  status: '状态',
  priority: '优先级',
  category_id: '分类',
}
const OP_LABELS: Record<ConditionOp, string> = {
  eq: '等于',
  ne: '不等于',
}
const ACTION_LABELS: Record<ActionType, string> = {
  set_priority: '设置优先级',
  set_status: '设置状态',
  set_category: '设置分类',
  set_assignee_user: '指派给用户',
  set_team: '指派给团队',
}
const STATUS_OPTIONS = ['OPEN', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETE', 'CANCELED']
const PRIORITY_OPTIONS = ['NONE', 'LOW', 'MEDIUM', 'HIGH']

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const workflows = ref<WorkflowRead[]>([])
const categories = ref<WorkOrderCategoryRead[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])

async function fetchWorkflows() {
  loading.value = true
  try {
    workflows.value = await listWorkflows()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchWorkflows()
  // 选项数据：失败不阻塞列表展示。
  try {
    ;[categories.value, users.value, teams.value] = await Promise.all([
      listWorkOrderCategories(),
      listUsers(),
      listTeams(),
    ])
  } catch {
    // ignore — selects 仍可手填/留空
  }
})

// ── create / edit dialog ───────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  name: string
  enabled: boolean
  trigger: WorkflowTrigger
  conditions: WorkflowCondition[]
  actions: WorkflowAction[]
}

const form = reactive<FormState>({
  name: '',
  enabled: true,
  trigger: 'WORK_ORDER_CREATED',
  conditions: [],
  actions: [],
})

const DIALOG_TITLES: Record<DialogMode, string> = {
  create: '新建工作流',
  edit: '编辑工作流',
}

function resetForm() {
  form.name = ''
  form.enabled = true
  form.trigger = 'WORK_ORDER_CREATED'
  form.conditions = []
  form.actions = []
}

function addCondition() {
  form.conditions.push({ field: 'priority', op: 'eq', value: null })
}
function removeCondition(idx: number) {
  form.conditions.splice(idx, 1)
}
function addAction() {
  form.actions.push({ type: 'set_priority', value: null })
}
function removeAction(idx: number) {
  form.actions.splice(idx, 1)
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: WorkflowRead) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.name = row.name
  form.enabled = row.enabled
  form.trigger = row.trigger
  form.conditions = row.conditions.map((c) => ({ ...c }))
  form.actions = row.actions.map((a) => ({ ...a }))
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写工作流名称')
    return
  }
  submitting.value = true
  try {
    const conditions = form.conditions.map((c) => ({ ...c }))
    const actions = form.actions.map((a) => ({ ...a }))
    if (dialogMode.value === 'create') {
      const payload: WorkflowCreate = {
        name: form.name,
        enabled: form.enabled,
        trigger: form.trigger,
        conditions,
        actions,
      }
      await createWorkflow(payload)
      ElMessage.success('工作流创建成功')
    } else {
      if (!editingId.value) return
      const payload: WorkflowUpdate = {
        name: form.name,
        enabled: form.enabled,
        trigger: form.trigger,
        conditions,
        actions,
      }
      await updateWorkflow(editingId.value, payload)
      ElMessage.success('工作流更新成功')
    }
    dialogVisible.value = false
    await fetchWorkflows()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── enable toggle ──────────────────────────────────────────
async function toggleEnabled(row: WorkflowRead) {
  try {
    await updateWorkflow(row.id, { enabled: !row.enabled })
    ElMessage.success(row.enabled ? '已停用' : '已启用')
    await fetchWorkflows()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: WorkflowRead) {
  try {
    await ElMessageBox.confirm(`确认删除工作流「${row.name}」？`, '删除工作流', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteWorkflow(row.id)
    ElMessage.success('已删除')
    await fetchWorkflows()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="workflows-view">
    <h2 class="page-title">工作流</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button
        v-if="auth.hasPermission('workflow.manage')"
        type="primary"
        @click="openCreate"
      >
        新建工作流
      </el-button>
    </div>

    <!-- table -->
    <el-table v-loading="loading" :data="workflows" border style="width: 100%; margin-top: 16px">
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="触发时机" min-width="160">
        <template #default="{ row }">{{ TRIGGER_LABELS[row.trigger as WorkflowTrigger] }}</template>
      </el-table-column>
      <el-table-column label="启用" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="条件数" width="90" align="center">
        <template #default="{ row }">{{ row.conditions.length }}</template>
      </el-table-column>
      <el-table-column label="动作数" width="90" align="center">
        <template #default="{ row }">{{ row.actions.length }}</template>
      </el-table-column>
      <el-table-column
        v-if="auth.hasPermission('workflow.manage')"
        label="操作"
        width="220"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="toggleEnabled(row)">
            {{ row.enabled ? '停用' : '启用' }}
          </el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="DIALOG_TITLES[dialogMode]"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="触发时机">
          <el-select v-model="form.trigger" style="width: 100%">
            <el-option
              v-for="(label, val) in TRIGGER_LABELS"
              :key="val"
              :label="label"
              :value="val"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>

        <!-- conditions -->
        <el-form-item label="条件">
          <div class="rows">
            <div v-for="(c, idx) in form.conditions" :key="`c-${idx}`" class="row">
              <el-select v-model="c.field" placeholder="字段" style="width: 120px">
                <el-option
                  v-for="(label, val) in FIELD_LABELS"
                  :key="val"
                  :label="label"
                  :value="val"
                />
              </el-select>
              <el-select v-model="c.op" placeholder="运算" style="width: 100px">
                <el-option
                  v-for="(label, val) in OP_LABELS"
                  :key="val"
                  :label="label"
                  :value="val"
                />
              </el-select>
              <el-select
                v-if="c.field === 'status'"
                v-model="c.value"
                placeholder="值"
                style="width: 160px"
              >
                <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="s" :value="s" />
              </el-select>
              <el-select
                v-else-if="c.field === 'priority'"
                v-model="c.value"
                placeholder="值"
                style="width: 160px"
              >
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p" :label="p" :value="p" />
              </el-select>
              <el-select
                v-else
                v-model="c.value"
                placeholder="分类"
                clearable
                style="width: 160px"
              >
                <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
              </el-select>
              <el-button link type="danger" @click="removeCondition(idx)">移除</el-button>
            </div>
            <el-button link type="primary" @click="addCondition">+ 添加条件</el-button>
          </div>
        </el-form-item>

        <!-- actions -->
        <el-form-item label="动作">
          <div class="rows">
            <div v-for="(a, idx) in form.actions" :key="`a-${idx}`" class="row">
              <el-select v-model="a.type" placeholder="动作" style="width: 140px">
                <el-option
                  v-for="(label, val) in ACTION_LABELS"
                  :key="val"
                  :label="label"
                  :value="val"
                />
              </el-select>
              <el-select
                v-if="a.type === 'set_status'"
                v-model="a.value"
                placeholder="目标状态"
                style="width: 200px"
              >
                <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="s" :value="s" />
              </el-select>
              <el-select
                v-else-if="a.type === 'set_priority'"
                v-model="a.value"
                placeholder="目标优先级"
                style="width: 200px"
              >
                <el-option v-for="p in PRIORITY_OPTIONS" :key="p" :label="p" :value="p" />
              </el-select>
              <el-select
                v-else-if="a.type === 'set_category'"
                v-model="a.value"
                placeholder="目标分类"
                clearable
                style="width: 200px"
              >
                <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
              </el-select>
              <el-select
                v-else-if="a.type === 'set_assignee_user'"
                v-model="a.value"
                placeholder="目标用户"
                filterable
                style="width: 200px"
              >
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
              <el-select
                v-else
                v-model="a.value"
                placeholder="目标团队"
                filterable
                style="width: 200px"
              >
                <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
              <el-button link type="danger" @click="removeAction(idx)">移除</el-button>
            </div>
            <el-button link type="primary" @click="addAction">+ 添加动作</el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.workflows-view {
  max-width: 1100px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
