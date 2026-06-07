<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import {
  listCustomFields,
  createCustomField,
  updateCustomField,
  archiveCustomField,
  restoreCustomField,
  deleteCustomField,
  reorderCustomFields,
} from '@/api/customFields'
import type { CustomFieldDef, CustomFieldType, CustomFieldEntity, CustomFieldOption } from '@/types/customField'
import { useAuthStore } from '@/store/auth'

const FIELD_TYPE_LABELS: Record<string, string> = {
  text: '文本',
  number: '数字',
  date: '日期',
  select: '单选',
  multi_select: '多选',
  checkbox: '复选框',
  textarea: '长文本',
}

const FIELD_TYPE_OPTIONS = Object.entries(FIELD_TYPE_LABELS).map(([value, label]) => ({ value, label }))

const ENTITY_OPTIONS: { value: CustomFieldEntity; label: string }[] = [
  { value: 'work_order', label: '工单' },
  { value: 'asset', label: '资产' },
  { value: 'request', label: '请求' },
  { value: 'location', label: '位置' },
  { value: 'part', label: '备件' },
]

const auth = useAuthStore()
const canEdit = ref(auth.hasPermission('company.settings'))

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const entityType = ref<CustomFieldEntity>('work_order')
const allFields = ref<CustomFieldDef[]>([])

const activeFields = computed(() =>
  allFields.value.filter(f => f.status === 'active'),
)
const archivedFields = computed(() =>
  allFields.value.filter(f => f.status === 'archived'),
)

// ── fetch ──────────────────────────────────────────────────
async function fetchFields() {
  loading.value = true
  try {
    allFields.value = await listCustomFields(entityType.value, true)
  } finally {
    loading.value = false
  }
}

function onEntityChange() {
  void fetchFields()
}

onMounted(fetchFields)

// ── dialog ─────────────────────────────────────────────────
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  name: string
  key: string
  field_type: CustomFieldType
  description: string
  required: boolean
  options: CustomFieldOption[]
  sort_order: number | undefined
}

const form = reactive<FormState>({
  name: '',
  key: '',
  field_type: 'text',
  description: '',
  required: false,
  options: [],
  sort_order: undefined,
})

const hasOptions = computed(() =>
  form.field_type === 'select' || form.field_type === 'multi_select' || form.field_type === 'checkbox',
)

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  Object.assign(form, {
    name: '',
    key: '',
    field_type: 'text',
    description: '',
    required: false,
    options: [],
    sort_order: undefined,
  })
  dialogVisible.value = true
}

function openEdit(row: CustomFieldDef) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    key: row.key,
    field_type: row.field_type,
    description: row.description ?? '',
    required: row.required,
    options: row.options ? row.options.map(o => ({ ...o })) : [],
    sort_order: row.sort_order,
  })
  dialogVisible.value = true
}

function addOption() {
  form.options.push({ value: Date.now().toString(), label: '' })
}

function removeOption(i: number) {
  form.options.splice(i, 1)
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写字段名')
    return
  }
  if (dialogMode.value === 'create' && !form.key.trim()) {
    ElMessage.warning('请填写 Key')
    return
  }
  if (hasOptions.value) {
    if (form.options.some(opt => !opt.label || opt.label.trim() === '')) {
      ElMessage.warning('选项名称不能为空')
      return
    }
    if (form.options.some(opt => !opt.value || opt.value.trim() === '')) {
      ElMessage.warning('选项值不能为空')
      return
    }
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createCustomField({
        entity_type: entityType.value,
        key: form.key,
        name: form.name,
        field_type: form.field_type,
        description: form.description || undefined,
        required: form.required,
        options: hasOptions.value ? form.options : undefined,
        sort_order: form.sort_order,
      })
      ElMessage.success('字段创建成功')
    } else {
      if (!editingId.value) return
      await updateCustomField(editingId.value, {
        name: form.name,
        description: form.description || undefined,
        required: form.required,
        options: hasOptions.value ? form.options : undefined,
        sort_order: form.sort_order,
      })
      ElMessage.success('字段更新成功')
    }
    dialogVisible.value = false
    await fetchFields()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── archive / restore ──────────────────────────────────────
async function handleArchive(row: CustomFieldDef) {
  try {
    await archiveCustomField(row.id)
    ElMessage.success('已归档')
    await fetchFields()
  } catch {
    // error handled by interceptor
  }
}

async function handleRestore(row: CustomFieldDef) {
  try {
    await restoreCustomField(row.id)
    ElMessage.success('已激活')
    await fetchFields()
  } catch {
    // error handled by interceptor
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: CustomFieldDef) {
  try {
    await ElMessageBox.confirm(
      `确认删除自定义字段「${row.name}」？此操作不可撤销。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteCustomField(row.id)
    ElMessage.success('已删除')
    await fetchFields()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// ── reorder ────────────────────────────────────────────────
async function moveField(index: number, direction: 'up' | 'down') {
  const arr = [...allFields.value.filter(f => f.status === 'active')]
  const swapIndex = direction === 'up' ? index - 1 : index + 1
  if (swapIndex < 0 || swapIndex >= arr.length) return
  ;[arr[index], arr[swapIndex]] = [arr[swapIndex], arr[index]]
  const archived = allFields.value.filter(f => f.status !== 'active')
  allFields.value = [...arr, ...archived]
  try {
    await reorderCustomFields(entityType.value, arr.map(f => f.id))
  } catch {
    // error handled by interceptor; refetch to restore state
    await fetchFields()
  }
}
</script>

<template>
  <div class="custom-fields-page">
    <h2 class="page-title">自定义字段</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-select
        v-model="entityType"
        style="width: 160px"
        @change="onEntityChange"
      >
        <el-option
          v-for="opt in ENTITY_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-button v-if="canEdit" type="primary" @click="openCreate">新建字段</el-button>
    </div>

    <!-- active fields table -->
    <el-table
      v-loading="loading"
      :data="activeFields"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="name" label="字段名" min-width="140" />
      <el-table-column prop="key" label="Key" min-width="140" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          {{ FIELD_TYPE_LABELS[row.field_type] ?? row.field_type }}
        </template>
      </el-table-column>
      <el-table-column label="必填" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.required ? 'danger' : 'info'" size="small">
            {{ row.required ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
            {{ row.status === 'active' ? '使用中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" align="center" fixed="right">
        <template #default="{ row, $index }">
          <template v-if="canEdit">
            <el-button
              :icon="ArrowUp"
              circle
              size="small"
              :disabled="$index === 0"
              @click="moveField($index, 'up')"
            />
            <el-button
              :icon="ArrowDown"
              circle
              size="small"
              :disabled="$index === activeFields.length - 1"
              @click="moveField($index, 'down')"
            />
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link @click="handleArchive(row)">归档</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
          <template v-else>
            <span class="readonly-hint">只读</span>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- archived fields collapse -->
    <el-collapse style="margin-top: 24px">
      <el-collapse-item name="archived">
        <template #title>
          <span class="collapse-title">已归档字段（{{ archivedFields.length }}）</span>
        </template>
        <el-table :data="archivedFields" border style="width: 100%">
          <el-table-column prop="name" label="字段名" min-width="140" />
          <el-table-column prop="key" label="Key" min-width="140" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              {{ FIELD_TYPE_LABELS[row.field_type] ?? row.field_type }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center" fixed="right">
            <template #default="{ row }">
              <template v-if="canEdit">
                <el-button link type="success" @click="handleRestore(row)">激活</el-button>
                <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              </template>
              <template v-else>
                <span class="readonly-hint">只读</span>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建自定义字段' : '编辑自定义字段'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px" @submit.prevent="submitForm">
        <el-form-item label="字段名" required>
          <el-input v-model="form.name" placeholder="请输入字段名" />
        </el-form-item>

        <el-form-item label="Key" required>
          <el-input
            v-model="form.key"
            placeholder="snake_case 格式，如 severity"
            :readonly="dialogMode === 'edit'"
          />
          <div v-if="dialogMode === 'edit'" class="hint">Key 创建后不可修改</div>
        </el-form-item>

        <el-form-item label="字段类型" required>
          <el-select
            v-model="form.field_type"
            :disabled="dialogMode === 'edit'"
            style="width: 100%"
          >
            <el-option
              v-for="t in FIELD_TYPE_OPTIONS"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
          <div v-if="dialogMode === 'edit'" class="hint">字段类型创建后不可修改</div>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="可选描述"
          />
        </el-form-item>

        <el-form-item label="必填">
          <el-switch v-model="form.required" />
        </el-form-item>

        <el-form-item label="排序值">
          <el-input-number v-model="form.sort_order" :min="0" :controls="true" />
        </el-form-item>

        <!-- options management for select / multi_select / checkbox -->
        <el-form-item v-if="hasOptions" label="选项">
          <div class="options-list">
            <div
              v-for="(opt, i) in form.options"
              :key="i"
              class="option-row"
            >
              <el-input v-model="opt.label" placeholder="显示名" style="flex: 1" />
              <el-input v-model="opt.value" placeholder="值" style="flex: 1; margin-left: 8px" />
              <el-button
                :icon="Close"
                circle
                size="small"
                style="margin-left: 8px; flex-shrink: 0"
                @click="removeOption(i)"
              />
            </div>
            <el-button style="margin-top: 8px" @click="addOption">添加选项</el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.custom-fields-page {
  max-width: 1100px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.collapse-title {
  font-size: 14px;
  font-weight: 500;
}
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.options-list {
  width: 100%;
}
.option-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}
.readonly-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
