<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getLocation, listLocationsMini } from '@/api/locations'
import { listVendorsMini } from '@/api/vendors'
import { listCustomersMini } from '@/api/customers'
import { listAssets } from '@/api/assets'
import { listWorkOrders } from '@/api/workOrders'
import {
  listFloorPlans,
  createFloorPlan,
  deleteFloorPlan,
} from '@/api/floorPlans'
import { WO_STATUS_LABELS, WO_STATUS_TAG } from '@/utils/workOrder'
import { useAuthStore } from '@/store/auth'
import EntityAttachments from '@/components/EntityAttachments.vue'
import type {
  LocationRead,
  LocationMini,
  AssetRead,
  AssetStatus,
  FloorPlanRead,
} from '@/types/maindata'
import type { VendorMini, CustomerMini } from '@/types/inventory'
import type { WorkOrderRead } from '@/types/workOrder'

// ── status labels ──────────────────────────────────────────
const STATUS_LABELS: Record<AssetStatus, string> = {
  OPERATIONAL: '运行中',
  STANDBY: '待机',
  MODERNIZATION: '改造中',
  INSPECTION_SCHEDULED: '待检',
  COMMISSIONING: '调试中',
  EMERGENCY_SHUTDOWN: '紧急停机',
  DOWN: '停机',
}
const UP_STATUSES = new Set<AssetStatus>([
  'OPERATIONAL',
  'STANDBY',
  'INSPECTION_SCHEDULED',
  'COMMISSIONING',
])
function statusTagType(s: AssetStatus): 'success' | 'danger' {
  return UP_STATUSES.has(s) ? 'success' : 'danger'
}
function assetStatusLabel(s: AssetStatus): string {
  return STATUS_LABELS[s]
}
function woStatusLabel(s: WorkOrderRead['status']): string {
  return WO_STATUS_LABELS[s]
}
function woStatusTag(s: WorkOrderRead['status']): string {
  return WO_STATUS_TAG[s]
}

// ── state ──────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const auth = useAuthStore()

const loading = ref(false)
const location = ref<LocationRead | null>(null)
const activeTab = ref('detail')

const locationsMini = ref<LocationMini[]>([])
const vendorsMini = ref<VendorMini[]>([])
const customersMini = ref<CustomerMini[]>([])

const canEdit = computed(() => auth.hasPermission('location.edit'))

function parentName(pid: string | null): string {
  if (!pid) return '—'
  return locationsMini.value.find((l) => l.id === pid)?.name ?? pid
}
function vendorNames(ids: string[]): string {
  if (!ids.length) return '—'
  return ids.map((i) => vendorsMini.value.find((v) => v.id === i)?.name ?? i).join('、')
}
function customerNames(ids: string[]): string {
  if (!ids.length) return '—'
  return ids.map((i) => customersMini.value.find((c) => c.id === i)?.name ?? i).join('、')
}

// ── load core ──────────────────────────────────────────────
async function load(): Promise<void> {
  loading.value = true
  try {
    location.value = await getLocation(id)
  } catch {
    ElMessage.error('加载位置失败，请重试')
    router.push('/assets/locations')
    return
  } finally {
    loading.value = false
  }
  // 关联名称映射非阻断；失败各自降级为 id。
  try {
    const [locs, vds, cus] = await Promise.all([
      listLocationsMini(),
      listVendorsMini(),
      listCustomersMini(),
    ])
    locationsMini.value = locs
    vendorsMini.value = vds
    customersMini.value = cus
  } catch {
    // 名称映射缺失时降级显示 id；不阻断详情。
  }
}

onMounted(load)

// ── 资产 tab（lazy）─────────────────────────────────────────
const assetLoading = ref(false)
const assetError = ref(false)
const assets = ref<AssetRead[]>([])
async function loadAssets(): Promise<void> {
  assetLoading.value = true
  assetError.value = false
  try {
    assets.value = await listAssets({ location_id: id })
  } catch {
    assetError.value = true
  } finally {
    assetLoading.value = false
  }
}
function openAsset(row: AssetRead): void {
  router.push(`/assets/${row.id}`)
}

// ── 工单 tab（lazy）─────────────────────────────────────────
const woLoading = ref(false)
const woError = ref(false)
const workOrders = ref<WorkOrderRead[]>([])
async function loadWorkOrders(): Promise<void> {
  woLoading.value = true
  woError.value = false
  try {
    workOrders.value = await listWorkOrders({ location_id: id })
  } catch {
    woError.value = true
  } finally {
    woLoading.value = false
  }
}
function openWorkOrder(row: WorkOrderRead): void {
  router.push(`/maintenance/work-orders/${row.id}`)
}

// ── 平面图 tab（lazy）───────────────────────────────────────
const fpLoading = ref(false)
const fpError = ref(false)
const floorPlans = ref<FloorPlanRead[]>([])
async function loadFloorPlans(): Promise<void> {
  fpLoading.value = true
  fpError.value = false
  try {
    floorPlans.value = await listFloorPlans(id)
  } catch {
    fpError.value = true
  } finally {
    fpLoading.value = false
  }
}

const fpDialogVisible = ref(false)
const fpSubmitting = ref(false)
const fpForm = ref<{ name: string; image_url: string; area: number | null }>({
  name: '',
  image_url: '',
  area: null,
})
function openCreateFloorPlan(): void {
  fpForm.value = { name: '', image_url: '', area: null }
  fpDialogVisible.value = true
}
async function submitFloorPlan(): Promise<void> {
  if (!fpForm.value.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  fpSubmitting.value = true
  try {
    await createFloorPlan(id, {
      name: fpForm.value.name.trim(),
      image_url: fpForm.value.image_url || null,
      area: fpForm.value.area,
    })
    ElMessage.success('平面图已新增')
    fpDialogVisible.value = false
    await loadFloorPlans()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    fpSubmitting.value = false
  }
}
async function removeFloorPlan(row: FloorPlanRead): Promise<void> {
  try {
    await deleteFloorPlan(id, row.id)
    ElMessage.success('已删除平面图')
    await loadFloorPlans()
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

// ── tab 切换：首次进入按需加载（各自降级，互不阻断）─────────
const loadedTabs = new Set<string>()
function onTabChange(name: string | number): void {
  const key = String(name)
  if (loadedTabs.has(key)) return
  loadedTabs.add(key)
  if (key === 'assets') loadAssets()
  else if (key === 'work-orders') loadWorkOrders()
  else if (key === 'floor-plans') loadFloorPlans()
}

defineExpose({
  load,
  loadAssets,
  loadWorkOrders,
  loadFloorPlans,
  submitFloorPlan,
  removeFloorPlan,
  openCreateFloorPlan,
  location,
  assets,
  workOrders,
  floorPlans,
  fpForm,
})
</script>

<template>
  <div v-loading="loading" class="page">
    <!-- 页头 -->
    <div class="page-header">
      <el-button link @click="router.push('/assets/locations')">← 返回位置列表</el-button>
      <div class="header-main">
        <span v-if="location" class="page-title">{{ location.name }}</span>
        <span v-if="location && location.address" class="header-sub">{{ location.address }}</span>
      </div>
    </div>

    <el-tabs v-model="activeTab" style="margin-top: 16px" @tab-change="onTabChange">
      <!-- 详情 -->
      <el-tab-pane label="详情" name="detail">
        <div v-if="location" class="detail-body">
          <img
            v-if="location.image_url"
            :src="location.image_url"
            alt="位置主图"
            class="location-image"
          />
          <el-descriptions :column="2" border>
            <el-descriptions-item label="名称">{{ location.name }}</el-descriptions-item>
            <el-descriptions-item label="编号">{{ location.custom_id }}</el-descriptions-item>
            <el-descriptions-item label="父位置">{{
              parentName(location.parent_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="地址">{{ location.address || '—' }}</el-descriptions-item>
            <el-descriptions-item label="经度">{{ location.longitude ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="纬度">{{ location.latitude ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="供应商">{{
              vendorNames(location.vendor_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="客户">{{
              customerNames(location.customer_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{
              location.description || '—'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-tab-pane>

      <!-- 资产 -->
      <el-tab-pane v-if="auth.hasPermission('asset.view')" label="资产" name="assets" lazy>
        <div v-loading="assetLoading">
          <el-alert
            v-if="assetError"
            type="error"
            :closable="false"
            title="加载资产失败"
            show-icon
          />
          <el-table :data="assets" @row-click="openAsset">
            <el-table-column prop="custom_id" label="编号" width="160" />
            <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)">{{
                  assetStatusLabel(row.status)
                }}</el-tag>
              </template>
            </el-table-column>
            <template #empty>暂无关联资产</template>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 工单 -->
      <el-tab-pane
        v-if="auth.hasPermission('work_order.view')"
        label="工单"
        name="work-orders"
        lazy
      >
        <div v-loading="woLoading">
          <el-alert
            v-if="woError"
            type="error"
            :closable="false"
            title="加载工单失败"
            show-icon
          />
          <el-table :data="workOrders" @row-click="openWorkOrder">
            <el-table-column prop="custom_id" label="编号" width="140" />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="woStatusTag(row.status)">{{ woStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <template #empty>暂无关联工单</template>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 文件 -->
      <el-tab-pane label="文件" name="files" lazy>
        <EntityAttachments entity-type="location" :entity-id="id" :editable="canEdit" />
      </el-tab-pane>

      <!-- 平面图 -->
      <el-tab-pane label="平面图" name="floor-plans" lazy>
        <div v-loading="fpLoading" class="fp-body">
          <el-alert
            v-if="fpError"
            type="error"
            :closable="false"
            title="加载平面图失败"
            show-icon
          />
          <div v-if="canEdit" class="fp-toolbar">
            <el-button type="primary" @click="openCreateFloorPlan">新增平面图</el-button>
          </div>
          <el-table :data="floorPlans">
            <el-table-column label="缩略图" width="120">
              <template #default="{ row }">
                <img v-if="row.image_url" :src="row.image_url" alt="平面图" class="fp-thumb" />
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column label="面积" width="140">
              <template #default="{ row }">{{ row.area ?? '—' }}</template>
            </el-table-column>
            <el-table-column
              v-if="canEdit"
              label="操作"
              width="120"
              align="center"
              fixed="right"
            >
              <template #default="{ row }">
                <el-popconfirm title="确定删除该平面图？" @confirm="removeFloorPlan(row)">
                  <template #reference>
                    <el-button link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
            <template #empty>暂无平面图</template>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增平面图对话框 -->
    <el-dialog
      v-model="fpDialogVisible"
      title="新增平面图"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px" @submit.prevent="submitFloorPlan">
        <el-form-item label="名称" required>
          <el-input v-model="fpForm.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="图片地址">
          <el-input v-model="fpForm.image_url" placeholder="请输入图片地址" />
        </el-form-item>
        <el-form-item label="面积">
          <el-input-number
            v-model="fpForm.area"
            :controls="false"
            :min="0"
            placeholder="请输入面积"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fpDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="fpSubmitting" @click="submitFloorPlan">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
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
  align-items: baseline;
  gap: 12px;
  flex: 1;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}
.header-sub {
  font-size: 14px;
  color: var(--text-secondary, #888);
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.location-image {
  max-width: 320px;
  max-height: 240px;
  object-fit: contain;
  border-radius: 6px;
}
.fp-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fp-toolbar {
  display: flex;
}
.fp-thumb {
  max-width: 80px;
  max-height: 60px;
  object-fit: contain;
  border-radius: 4px;
}
</style>
