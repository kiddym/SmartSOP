<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRoles, createRole, updateRole, deleteRole } from '@/api/roles'
import { listPermissions } from '@/api/permissions'
import type { RoleRead, RoleCreate, RoleUpdate, PermissionGroup } from '@/types/platform'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const roles = ref<RoleRead[]>([])
const permissionGroups = ref<PermissionGroup[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchRoles() {
  loading.value = true
  try {
    roles.value = await listRoles()
  } finally {
    loading.value = false
  }
}

async function fetchPermissionGroups() {
  permissionGroups.value = await listPermissions()
}

onMounted(async () => {
  await Promise.all([fetchRoles(), fetchPermissionGroups()])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  code: string
  name: string
  permissions: string[]
}

const form = reactive<FormState>({
  code: '',
  name: '',
  permissions: [],
})

const DIALOG_TITLES: Record<DialogMode, string> = {
  create: '新建角色',
  edit: '编辑角色',
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.permissions = []
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: RoleRead) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.code = row.code
  form.name = row.name
  form.permissions = [...row.permissions]
  dialogVisible.value = true
}

async function submitForm() {
  if (dialogMode.value === 'create' && !form.code.trim()) {
    ElMessage.warning('请填写角色标识')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写角色名称')
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const payload: RoleCreate = {
        code: form.code,
        name: form.name,
        permissions: [...form.permissions],
      }
      await createRole(payload)
      ElMessage.success('角色创建成功')
    } else {
      if (!editingId.value) return
      const payload: RoleUpdate = {
        name: form.name,
        permissions: [...form.permissions],
      }
      await updateRole(editingId.value, payload)
      ElMessage.success('角色更新成功')
    }
    dialogVisible.value = false
    await fetchRoles()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: RoleRead) {
  try {
    await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '删除角色', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteRole(row.id)
    ElMessage.success('已删除')
    await fetchRoles()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="roles-view">
    <h2 class="page-title">角色管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('role.manage')" type="primary" @click="openCreate">
        新建角色
      </el-button>
    </div>

    <!-- roles table -->
    <el-table v-loading="loading" :data="roles" border style="width: 100%; margin-top: 16px">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="code" label="标识" min-width="140" />
      <el-table-column label="类型" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.is_builtin ? 'info' : 'success'" size="small">
            {{ row.is_builtin ? '内置' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权限数" width="90" align="center">
        <template #default="{ row }">
          {{ row.permissions.length }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="auth.hasPermission('role.manage')"
        label="操作"
        width="160"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <el-tooltip :disabled="!row.is_builtin" content="内置角色不可修改" placement="top">
            <span>
              <el-button link type="primary" :disabled="row.is_builtin" @click="openEdit(row)">
                编辑
              </el-button>
            </span>
          </el-tooltip>
          <el-tooltip :disabled="!row.is_builtin" content="内置角色不可修改" placement="top">
            <span>
              <el-button link type="danger" :disabled="row.is_builtin" @click="handleDelete(row)">
                删除
              </el-button>
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="DIALOG_TITLES[dialogMode]"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="submitForm">
        <el-form-item v-if="dialogMode === 'create'" label="标识" required>
          <el-input v-model="form.code" placeholder="请输入角色标识" />
        </el-form-item>
        <el-form-item v-else label="标识">
          <span class="readonly-code">{{ form.code }}</span>
        </el-form-item>

        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>

        <el-form-item label="权限">
          <div class="perm-picker">
            <div v-for="grp in permissionGroups" :key="grp.group" class="perm-group">
              <div class="perm-group-title">{{ grp.group }}</div>
              <el-checkbox-group v-model="form.permissions">
                <el-checkbox v-for="perm in grp.permissions" :key="perm.code" :value="perm.code">
                  {{ perm.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
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
.roles-view {
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
.readonly-code {
  color: var(--text-secondary, #606266);
}
.perm-picker {
  width: 100%;
}
.perm-group {
  margin-bottom: 12px;
}
.perm-group-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-primary, #1a1a1a);
}
</style>
