<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, inviteUser, updateUser, deleteUser } from '@/api/users'
import { listRoles } from '@/api/roles'
import type { UserRead, UserCreate, UserInvite, UserUpdate, RoleRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const users = ref<UserRead[]>([])
const roles = ref<RoleRead[]>([])

function roleName(id: string | null): string {
  if (!id) return '—'
  return roles.value.find((r) => r.id === id)?.name ?? '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchUsers() {
  loading.value = true
  try {
    users.value = await listUsers()
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  roles.value = await listRoles()
}

onMounted(async () => {
  await Promise.all([fetchUsers(), fetchRoles()])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'invite' | 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('invite')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  email: string
  password: string
  name: string
  role_id: string | null
  status: 'active' | 'inactive'
}

const form = reactive<FormState>({
  email: '',
  password: '',
  name: '',
  role_id: null,
  status: 'active',
})

const DIALOG_TITLES: Record<DialogMode, string> = {
  invite: '邀请用户',
  create: '直接建号',
  edit: '编辑用户',
}

function resetForm() {
  form.email = ''
  form.password = ''
  form.name = ''
  form.role_id = null
  form.status = 'active'
}

function openInvite() {
  dialogMode.value = 'invite'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: UserRead) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.name = row.name
  form.role_id = row.role_id
  form.status = row.status
  dialogVisible.value = true
}

async function submitForm() {
  if (dialogMode.value !== 'edit' && !form.email.trim()) {
    ElMessage.warning('请填写邮箱')
    return
  }
  if (dialogMode.value === 'create' && !form.password.trim()) {
    ElMessage.warning('请填写密码')
    return
  }
  if (dialogMode.value !== 'invite' && !form.name.trim()) {
    ElMessage.warning('请填写姓名')
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'invite') {
      const payload: UserInvite = {
        email: form.email,
        role_id: form.role_id ?? undefined,
      }
      await inviteUser(payload)
      ElMessage.success('邀请已发送')
    } else if (dialogMode.value === 'create') {
      const payload: UserCreate = {
        email: form.email,
        password: form.password,
        name: form.name,
        role_id: form.role_id ?? undefined,
      }
      await createUser(payload)
      ElMessage.success('用户创建成功')
    } else {
      if (!editingId.value) return
      const payload: UserUpdate = {
        name: form.name,
        role_id: form.role_id,
        status: form.status,
      }
      if (form.password.trim()) {
        payload.password = form.password
      }
      await updateUser(editingId.value, payload)
      ElMessage.success('用户更新成功')
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: UserRead) {
  try {
    await ElMessageBox.confirm(`确认删除用户「${row.name}」？`, '删除用户', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteUser(row.id)
    ElMessage.success('已删除')
    await fetchUsers()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="users-view">
    <h2 class="page-title">用户管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('user.create')" type="primary" @click="openInvite">
        邀请用户
      </el-button>
      <el-button v-if="auth.hasPermission('user.create')" @click="openCreate"> 直接建号 </el-button>
    </div>

    <!-- users table -->
    <el-table v-loading="loading" :data="users" border style="width: 100%; margin-top: 16px">
      <el-table-column prop="name" label="姓名" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" min-width="120">
        <template #default="{ row }">
          {{ roleName(row.role_id) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" width="160" align="center">
        <template #default="{ row }">
          {{ row.last_login_at ? formatDateTime(row.last_login_at) : '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('user.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('user.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- invite / create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="DIALOG_TITLES[dialogMode]"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="submitForm">
        <el-form-item v-if="dialogMode !== 'edit'" label="邮箱" required>
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item v-if="dialogMode === 'create'" label="密码" required>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入初始密码"
          />
        </el-form-item>

        <el-form-item v-if="dialogMode !== 'invite'" label="姓名" required>
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>

        <el-form-item label="角色">
          <el-select v-model="form.role_id" placeholder="请选择角色" clearable style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="dialogMode === 'edit'" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="dialogMode === 'edit'" label="新密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="留空则不修改"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ dialogMode === 'invite' ? '发送邀请' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.users-view {
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
</style>
