<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listLocations, createLocation, updateLocation, deleteLocation } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import type { LocationRead, LocationCreate, LocationUpdate } from '@/types/maindata'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { buildTree, collectDescendantIds } from '@/utils/tree'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const locations = ref<LocationRead[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])

const tree = computed(() => buildTree(locations.value))

// ── fetch ──────────────────────────────────────────────────
async function fetchLocations() {
  loading.value = true
  try {
    locations.value = await listLocations()
  } finally {
    loading.value = false
  }
}

async function fetchUsers() {
  users.value = await listUsers()
}

async function fetchTeams() {
  teams.value = await listTeams()
}

onMounted(async () => {
  await Promise.all([fetchLocations(), fetchUsers(), fetchTeams()])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  description: string
  parent_id: string | null
  address: string
  longitude: number | null
  latitude: number | null
  assigned_user_ids: string[]
  team_ids: string[]
}

const form = reactive<FormState>({
  name: '',
  description: '',
  parent_id: null,
  address: '',
  longitude: null,
  latitude: null,
  assigned_user_ids: [],
  team_ids: [],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建位置' : '编辑位置'))

// 编辑时排除自身 + 全部后代，防止成环。
const parentOptions = computed(() => {
  const excluded =
    dialogMode.value === 'edit' && editingId.value
      ? collectDescendantIds(locations.value, editingId.value)
      : new Set<string>()
  return locations.value.filter((l) => !excluded.has(l.id))
})

function resetForm() {
  form.name = ''
  form.description = ''
  form.parent_id = null
  form.address = ''
  form.longitude = null
  form.latitude = null
  form.assigned_user_ids = []
  form.team_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: LocationRead) {
  resetForm()
  Object.assign(form, {
    name: row.name,
    description: row.description,
    parent_id: row.parent_id,
    address: row.address,
    longitude: row.longitude,
    latitude: row.latitude,
    assigned_user_ids: [...row.assigned_user_ids],
    team_ids: [...row.team_ids],
  })
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }

  submitting.value = true
  try {
    const payload: LocationCreate | LocationUpdate = {
      name: form.name,
      description: form.description,
      parent_id: form.parent_id,
      address: form.address,
      longitude: form.longitude,
      latitude: form.latitude,
      assigned_user_ids: form.assigned_user_ids,
      team_ids: form.team_ids,
    }
    if (dialogMode.value === 'create') {
      await createLocation(payload as LocationCreate)
      ElMessage.success('位置创建成功')
    } else {
      if (!editingId.value) return
      await updateLocation(editingId.value, payload)
      ElMessage.success('位置更新成功')
    }
    dialogVisible.value = false
    await fetchLocations()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// expose for tests (cycle-prevention assertion on parentOptions)
defineExpose({ parentOptions, openEdit })

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: LocationRead) {
  try {
    await ElMessageBox.confirm(`确认删除位置「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteLocation(row.id)
    ElMessage.success('已删除')
    await fetchLocations()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">位置管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('location.create')" type="primary" @click="openCreate">
        新建位置
      </el-button>
    </div>

    <!-- locations tree table -->
    <el-table
      v-loading="loading"
      :data="tree"
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="name" label="名称" min-width="200" />
      <el-table-column prop="custom_id" label="编号" min-width="120" />
      <el-table-column prop="address" label="地址" min-width="160" />
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('location.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('location.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>

        <el-form-item label="父位置">
          <el-select
            v-model="form.parent_id"
            placeholder="请选择父位置"
            clearable
            style="width: 100%"
          >
            <el-option v-for="l in parentOptions" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="请输入地址" />
        </el-form-item>

        <el-form-item label="经度">
          <el-input-number
            v-model="form.longitude"
            :controls="false"
            placeholder="请输入经度"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="纬度">
          <el-input-number
            v-model="form.latitude"
            :controls="false"
            placeholder="请输入纬度"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="负责人">
          <el-select
            v-model="form.assigned_user_ids"
            multiple
            filterable
            placeholder="请选择负责人"
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="团队">
          <el-select v-model="form.team_ids" multiple placeholder="请选择团队" style="width: 100%">
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm"> 保存 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
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
