<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTeams, createTeam, updateTeam, deleteTeam, setTeamMembers } from '@/api/teams'
import { listUsers } from '@/api/users'
import type { TeamRead, TeamCreate, TeamUpdate, UserRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const teams = ref<TeamRead[]>([])
const users = ref<UserRead[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchTeams() {
  loading.value = true
  try {
    teams.value = await listTeams()
  } finally {
    loading.value = false
  }
}

async function fetchUsers() {
  users.value = await listUsers()
}

onMounted(async () => {
  await Promise.all([fetchTeams(), fetchUsers()])
})

// ── create / edit dialog ───────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const submitting = ref(false)
const editingId = ref<string | null>(null)

interface FormState {
  name: string
  description: string
}

const form = reactive<FormState>({
  name: '',
  description: '',
})

const DIALOG_TITLES: Record<DialogMode, string> = {
  create: '新建团队',
  edit: '编辑团队',
}

function resetForm() {
  form.name = ''
  form.description = ''
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: TeamRead) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  resetForm()
  form.name = row.name
  form.description = row.description
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写团队名称')
    return
  }

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const payload: TeamCreate = {
        name: form.name,
        description: form.description,
      }
      await createTeam(payload)
      ElMessage.success('团队创建成功')
    } else {
      if (!editingId.value) return
      const payload: TeamUpdate = {
        name: form.name,
        description: form.description,
      }
      await updateTeam(editingId.value, payload)
      ElMessage.success('团队更新成功')
    }
    dialogVisible.value = false
    await fetchTeams()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── member management dialog ────────────────────────────────
const memberDialogVisible = ref(false)
const memberTeamId = ref<string | null>(null)
const memberTeamName = ref('')
const memberSubmitting = ref(false)
const selectedUserIds = ref<string[]>([])

function openMembers(row: TeamRead) {
  memberTeamId.value = row.id
  memberTeamName.value = row.name
  selectedUserIds.value = [...row.member_ids]
  memberDialogVisible.value = true
}

async function submitMembers() {
  if (!memberTeamId.value) return
  memberSubmitting.value = true
  try {
    await setTeamMembers(memberTeamId.value, [...selectedUserIds.value])
    ElMessage.success('成员已更新')
    memberDialogVisible.value = false
    await fetchTeams()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    memberSubmitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: TeamRead) {
  try {
    await ElMessageBox.confirm(`确认删除团队「${row.name}」？`, '删除团队', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteTeam(row.id)
    ElMessage.success('已删除')
    await fetchTeams()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="teams-view">
    <h2 class="page-title">团队管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('team.manage')" type="primary" @click="openCreate">
        新建团队
      </el-button>
    </div>

    <!-- teams table -->
    <el-table v-loading="loading" :data="teams" border style="width: 100%; margin-top: 16px">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="成员数" width="90" align="center">
        <template #default="{ row }">
          {{ row.member_ids.length }}
        </template>
      </el-table-column>
      <el-table-column
        v-if="auth.hasPermission('team.manage')"
        label="操作"
        width="200"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openMembers(row)">成员</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="DIALOG_TITLES[dialogMode]"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入团队名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- member management dialog -->
    <el-dialog
      v-model="memberDialogVisible"
      :title="`成员管理 — ${memberTeamName}`"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="成员">
          <el-select
            v-model="selectedUserIds"
            multiple
            filterable
            placeholder="请选择成员"
            style="width: 100%"
          >
            <el-option
              v-for="u in users"
              :key="u.id"
              :label="`${u.name}（${u.email}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="memberDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="memberSubmitting" @click="submitMembers"
          >保存</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.teams-view {
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
