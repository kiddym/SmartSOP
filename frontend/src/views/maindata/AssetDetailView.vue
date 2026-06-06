<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAsset } from '@/api/assets'
import { listAssetCategories } from '@/api/assetCategories'
import { listLocationsMini } from '@/api/locations'
import { listVendorsMini } from '@/api/vendors'
import { listCustomersMini } from '@/api/customers'
import { listPartsMini } from '@/api/parts'
import { listWorkOrders } from '@/api/workOrders'
import { listMeters } from '@/api/meters'
import { getDeprecation, putDeprecation, deleteDeprecation } from '@/api/deprecations'
import { WO_STATUS_LABELS, WO_STATUS_TAG } from '@/utils/workOrder'
import { useAuthStore } from '@/store/auth'
import EntityAttachments from '@/components/EntityAttachments.vue'
import type {
  AssetRead,
  AssetStatus,
  AssetCategoryRead,
  LocationMini,
} from '@/types/maindata'
import type { VendorMini, CustomerMini, PartMini } from '@/types/inventory'
import type { WorkOrderRead, WorkOrderPriority } from '@/types/workOrder'
import type { MeterRead } from '@/types/maintenance'
import type { DeprecationRead, DeprecationUpdate } from '@/types/deprecation'

// ── status / priority labels ───────────────────────────────
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
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}
function statusTagType(s: AssetStatus): 'success' | 'danger' {
  return UP_STATUSES.has(s) ? 'success' : 'danger'
}
function woStatusLabel(s: WorkOrderRead['status']): string {
  return WO_STATUS_LABELS[s]
}
function woStatusTag(s: WorkOrderRead['status']): string {
  return WO_STATUS_TAG[s]
}
function priorityLabel(p: WorkOrderPriority): string {
  return PRIORITY_LABELS[p]
}

// ── state ──────────────────────────────────────────────────
const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const auth = useAuthStore()

const loading = ref(false)
const asset = ref<AssetRead | null>(null)
const activeTab = ref('detail')

const categories = ref<AssetCategoryRead[]>([])
const locationsMini = ref<LocationMini[]>([])
const vendorsMini = ref<VendorMini[]>([])
const customersMini = ref<CustomerMini[]>([])
const partsMini = ref<PartMini[]>([])

const canEdit = computed(() => auth.hasPermission('asset.edit'))

function categoryName(cid: string | null): string {
  if (!cid) return '—'
  return categories.value.find((c) => c.id === cid)?.name ?? '—'
}
function locationName(lid: string | null): string {
  if (!lid) return '—'
  return locationsMini.value.find((l) => l.id === lid)?.name ?? '—'
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
    asset.value = await getAsset(id)
  } catch {
    ElMessage.error('加载资产失败，请重试')
    router.push('/assets')
    return
  } finally {
    loading.value = false
  }
  // 关联映射（名称展示）非阻断加载，失败各自降级为 id。
  try {
    const [cats, locs, vds, cus, prts] = await Promise.all([
      listAssetCategories(),
      listLocationsMini(),
      listVendorsMini(),
      listCustomersMini(),
      listPartsMini(),
    ])
    categories.value = cats
    locationsMini.value = locs
    vendorsMini.value = vds
    customersMini.value = cus
    partsMini.value = prts
  } catch {
    // 名称映射缺失时降级显示 id；不阻断详情。
  }
}

onMounted(load)

// ── 备件 tab ───────────────────────────────────────────────
const relatedParts = computed(() => {
  const ids = asset.value?.part_ids ?? []
  return ids.map((pid) => {
    const p = partsMini.value.find((x) => x.id === pid)
    return { id: pid, custom_id: p?.custom_id ?? '—', name: p?.name ?? '(已删除)' }
  })
})

// ── 工单 tab（lazy）─────────────────────────────────────────
const woLoading = ref(false)
const woError = ref(false)
const workOrders = ref<WorkOrderRead[]>([])
async function loadWorkOrders(): Promise<void> {
  woLoading.value = true
  woError.value = false
  try {
    workOrders.value = await listWorkOrders({ asset_id: id })
  } catch {
    woError.value = true
  } finally {
    woLoading.value = false
  }
}
function openWorkOrder(row: WorkOrderRead): void {
  router.push(`/maintenance/work-orders/${row.id}`)
}

// ── 计量 tab（lazy）─────────────────────────────────────────
const meterLoading = ref(false)
const meterError = ref(false)
const meters = ref<MeterRead[]>([])
async function loadMeters(): Promise<void> {
  meterLoading.value = true
  meterError.value = false
  try {
    meters.value = await listMeters({ asset_id: id })
  } catch {
    meterError.value = true
  } finally {
    meterLoading.value = false
  }
}

// ── 折旧 tab（lazy）─────────────────────────────────────────
const depLoading = ref(false)
const depError = ref(false)
const depSaving = ref(false)
const deprecation = ref<DeprecationRead | null>(null)
const depForm = ref<DeprecationUpdate>({
  purchase_price: null,
  purchase_date: null,
  residual_value: null,
  useful_life_years: null,
  rate: null,
})
function syncDepForm(d: DeprecationRead | null): void {
  depForm.value = {
    purchase_price: d?.purchase_price ?? null,
    purchase_date: d?.purchase_date ?? null,
    residual_value: d?.residual_value ?? null,
    useful_life_years: d?.useful_life_years ?? null,
    rate: d?.rate ?? null,
  }
}
async function loadDeprecation(): Promise<void> {
  depLoading.value = true
  depError.value = false
  try {
    deprecation.value = await getDeprecation(id)
    syncDepForm(deprecation.value)
  } catch {
    depError.value = true
  } finally {
    depLoading.value = false
  }
}
async function saveDeprecation(): Promise<void> {
  depSaving.value = true
  try {
    deprecation.value = await putDeprecation(id, {
      purchase_price: depForm.value.purchase_price || null,
      purchase_date: depForm.value.purchase_date || null,
      residual_value: depForm.value.residual_value || null,
      useful_life_years: depForm.value.useful_life_years ?? null,
      rate: depForm.value.rate || null,
    })
    syncDepForm(deprecation.value)
    ElMessage.success('折旧信息已保存')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    depSaving.value = false
  }
}
async function removeDeprecation(): Promise<void> {
  try {
    await deleteDeprecation(id)
    deprecation.value = null
    syncDepForm(null)
    ElMessage.success('已删除折旧信息')
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

// ── tab 切换：首次进入对应 tab 时按需加载（各自降级，不互相阻断）─
const loadedTabs = new Set<string>()
function onTabChange(name: string | number): void {
  const key = String(name)
  if (loadedTabs.has(key)) return
  loadedTabs.add(key)
  if (key === 'work-orders') loadWorkOrders()
  else if (key === 'meters') loadMeters()
  else if (key === 'deprecation') loadDeprecation()
}

defineExpose({
  load,
  loadWorkOrders,
  loadMeters,
  loadDeprecation,
  saveDeprecation,
  removeDeprecation,
  asset,
  workOrders,
  meters,
  deprecation,
  depForm,
  relatedParts,
})
</script>

<template>
  <div v-loading="loading" class="page">
    <!-- 页头 -->
    <div class="page-header">
      <el-button link @click="router.push('/assets')">← 返回资产列表</el-button>
      <div class="header-main">
        <span v-if="asset" class="page-title">{{ asset.custom_id }} {{ asset.name }}</span>
        <el-tag v-if="asset" :type="statusTagType(asset.status)" style="margin-left: 12px">
          {{ STATUS_LABELS[asset.status] }}
        </el-tag>
      </div>
    </div>

    <el-tabs v-model="activeTab" style="margin-top: 16px" @tab-change="onTabChange">
      <!-- 详情 -->
      <el-tab-pane label="详情" name="detail">
        <div v-if="asset" class="detail-body">
          <img
            v-if="asset.image_url"
            :src="asset.image_url"
            alt="资产主图"
            class="asset-image"
          />
          <el-descriptions :column="2" border>
            <el-descriptions-item label="名称">{{ asset.name }}</el-descriptions-item>
            <el-descriptions-item label="编号">{{ asset.custom_id }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTagType(asset.status)">{{
                STATUS_LABELS[asset.status]
              }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="分类">{{
              categoryName(asset.category_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="位置">{{
              locationName(asset.location_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="区域">{{ asset.area || '—' }}</el-descriptions-item>
            <el-descriptions-item label="制造商">{{
              asset.manufacturer || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ asset.model || '—' }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{
              asset.serial_number || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="功率">{{ asset.power || '—' }}</el-descriptions-item>
            <el-descriptions-item label="供应商">{{
              vendorNames(asset.vendor_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="客户">{{
              customerNames(asset.customer_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{
              asset.description || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="更多信息" :span="2">{{
              asset.additional_infos || '—'
            }}</el-descriptions-item>
          </el-descriptions>
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
            <el-table-column label="优先级" width="100">
              <template #default="{ row }">{{ priorityLabel(row.priority) }}</template>
            </el-table-column>
            <template #empty>暂无关联工单</template>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 备件 -->
      <el-tab-pane v-if="auth.hasPermission('part.view')" label="备件" name="parts" lazy>
        <el-table :data="relatedParts">
          <el-table-column prop="custom_id" label="编号" width="160" />
          <el-table-column prop="name" label="名称" min-width="200" />
          <template #empty>暂无关联备件</template>
        </el-table>
      </el-tab-pane>

      <!-- 文件 -->
      <el-tab-pane label="文件" name="files" lazy>
        <EntityAttachments entity-type="asset" :entity-id="id" :editable="canEdit" />
      </el-tab-pane>

      <!-- 计量 -->
      <el-tab-pane v-if="auth.hasPermission('meter.view')" label="计量" name="meters" lazy>
        <div v-loading="meterLoading">
          <el-alert
            v-if="meterError"
            type="error"
            :closable="false"
            title="加载计量器失败"
            show-icon
          />
          <el-table :data="meters">
            <el-table-column prop="custom_id" label="编号" width="140" />
            <el-table-column prop="name" label="名称" min-width="180" />
            <el-table-column prop="unit" label="单位" width="120" />
            <el-table-column label="更新频率(天)" width="140">
              <template #default="{ row }">{{ row.update_frequency_days ?? '—' }}</template>
            </el-table-column>
            <template #empty>暂无关联计量器</template>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 折旧 -->
      <el-tab-pane label="折旧" name="deprecation" lazy>
        <div v-loading="depLoading" class="dep-body">
          <el-alert
            v-if="depError"
            type="error"
            :closable="false"
            title="加载折旧信息失败"
            show-icon
          />
          <el-form label-width="120px" style="max-width: 480px">
            <el-form-item label="购置价">
              <el-input
                v-model="depForm.purchase_price"
                :disabled="!canEdit"
                placeholder="请输入购置价"
              />
            </el-form-item>
            <el-form-item label="购置日期">
              <el-date-picker
                v-model="depForm.purchase_date"
                :disabled="!canEdit"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择购置日期"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="残值">
              <el-input
                v-model="depForm.residual_value"
                :disabled="!canEdit"
                placeholder="请输入残值"
              />
            </el-form-item>
            <el-form-item label="使用年限(年)">
              <el-input-number
                v-model="depForm.useful_life_years"
                :disabled="!canEdit"
                :min="0"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="折旧率">
              <el-input v-model="depForm.rate" :disabled="!canEdit" placeholder="请输入折旧率" />
            </el-form-item>
            <el-form-item label="当前价值">
              <span class="dep-current">{{ deprecation?.current_value ?? '—' }}</span>
            </el-form-item>
          </el-form>
          <div v-if="canEdit" class="dep-actions">
            <el-button type="primary" :loading="depSaving" @click="saveDeprecation">
              保存
            </el-button>
            <el-popconfirm
              v-if="deprecation"
              title="确定删除折旧信息？"
              @confirm="removeDeprecation"
            >
              <template #reference>
                <el-button type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
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
  align-items: center;
  flex: 1;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.asset-image {
  max-width: 320px;
  max-height: 240px;
  object-fit: contain;
  border-radius: 6px;
}
.dep-body {
  padding-top: 8px;
}
.dep-current {
  font-weight: 600;
}
.dep-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}
</style>
