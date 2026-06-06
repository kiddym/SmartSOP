<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPart, listPartWorkOrders } from '@/api/parts'
import { listPartCategories } from '@/api/partCategories'
import { listAssetsMini } from '@/api/assets'
import { listVendorsMini } from '@/api/vendors'
import { listCustomersMini } from '@/api/customers'
import { WO_STATUS_LABELS, WO_STATUS_TAG } from '@/utils/workOrder'
import { useAuthStore } from '@/store/auth'
import EntityAttachments from '@/components/EntityAttachments.vue'
import type { PartRead, PartCategoryRead, VendorMini, CustomerMini } from '@/types/inventory'
import type { AssetMini } from '@/types/maindata'
import type { WorkOrderRead } from '@/types/workOrder'

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
const part = ref<PartRead | null>(null)
const activeTab = ref('detail')

const categories = ref<PartCategoryRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const vendorsMini = ref<VendorMini[]>([])
const customersMini = ref<CustomerMini[]>([])

const canEdit = computed(() => auth.hasPermission('part.edit'))

function categoryName(cid: string | null): string {
  if (!cid) return '—'
  return categories.value.find((c) => c.id === cid)?.name ?? '—'
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
    part.value = await getPart(id)
  } catch {
    ElMessage.error('加载备件失败，请重试')
    router.push('/inventory/parts')
    return
  } finally {
    loading.value = false
  }
  // 关联名称映射非阻断；失败各自降级为 id。
  try {
    const [cats, asts, vds, cus] = await Promise.all([
      listPartCategories(),
      listAssetsMini(),
      listVendorsMini(),
      listCustomersMini(),
    ])
    categories.value = cats
    assetsMini.value = asts
    vendorsMini.value = vds
    customersMini.value = cus
  } catch {
    // 名称映射缺失时降级显示 id；不阻断详情。
  }
}

onMounted(load)

// ── 资产 tab（只读，由 asset_ids 映射）──────────────────────
const relatedAssets = computed(() => {
  const ids = part.value?.asset_ids ?? []
  return ids.map((aid) => {
    const a = assetsMini.value.find((x) => x.id === aid)
    return { id: aid, custom_id: a?.custom_id ?? '—', name: a?.name ?? '(已删除)' }
  })
})
function openAsset(row: { id: string }): void {
  router.push(`/assets/${row.id}`)
}

// ── 工单 tab（lazy 反查）────────────────────────────────────
const woLoading = ref(false)
const woError = ref(false)
const workOrders = ref<WorkOrderRead[]>([])
async function loadWorkOrders(): Promise<void> {
  woLoading.value = true
  woError.value = false
  try {
    workOrders.value = await listPartWorkOrders(id)
  } catch {
    woError.value = true
  } finally {
    woLoading.value = false
  }
}
function openWorkOrder(row: WorkOrderRead): void {
  router.push(`/maintenance/work-orders/${row.id}`)
}

// ── tab 切换：首次进入按需加载（各自降级，互不阻断）─────────
const loadedTabs = new Set<string>()
function onTabChange(name: string | number): void {
  const key = String(name)
  if (loadedTabs.has(key)) return
  loadedTabs.add(key)
  if (key === 'work-orders') loadWorkOrders()
}

defineExpose({
  load,
  loadWorkOrders,
  part,
  workOrders,
  relatedAssets,
})
</script>

<template>
  <div v-loading="loading" class="page">
    <!-- 页头 -->
    <div class="page-header">
      <el-button link @click="router.push('/inventory/parts')">← 返回备件列表</el-button>
      <div class="header-main">
        <span v-if="part" class="page-title">{{ part.custom_id }} {{ part.name }}</span>
        <span v-if="part" class="header-sub">库存 {{ part.quantity }} {{ part.unit }}</span>
        <el-tag v-if="part && part.is_low_stock" type="danger" style="margin-left: 4px">
          低库存
        </el-tag>
      </div>
    </div>

    <el-tabs v-model="activeTab" style="margin-top: 16px" @tab-change="onTabChange">
      <!-- 详情 -->
      <el-tab-pane label="详情" name="detail">
        <div v-if="part" class="detail-body">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="编号">{{ part.custom_id }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ part.name }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{
              categoryName(part.category_id)
            }}</el-descriptions-item>
            <el-descriptions-item label="单位">{{ part.unit || '—' }}</el-descriptions-item>
            <el-descriptions-item label="单价">{{ part.cost }}</el-descriptions-item>
            <el-descriptions-item label="库存量">{{ part.quantity }}</el-descriptions-item>
            <el-descriptions-item label="最低库存">{{ part.min_quantity }}</el-descriptions-item>
            <el-descriptions-item label="低库存">
              <el-tag v-if="part.is_low_stock" type="danger">是</el-tag>
              <span v-else>否</span>
            </el-descriptions-item>
            <el-descriptions-item label="条码">{{ part.barcode || '—' }}</el-descriptions-item>
            <el-descriptions-item label="库区/货位">{{ part.area || '—' }}</el-descriptions-item>
            <el-descriptions-item label="供应商">{{
              vendorNames(part.vendor_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="客户">{{
              customerNames(part.customer_ids)
            }}</el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{
              part.description || '—'
            }}</el-descriptions-item>
            <el-descriptions-item label="附加信息" :span="2">{{
              part.additional_infos || '—'
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
            <template #empty>暂无关联工单</template>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 资产 -->
      <el-tab-pane v-if="auth.hasPermission('asset.view')" label="资产" name="assets" lazy>
        <el-table :data="relatedAssets" @row-click="openAsset">
          <el-table-column prop="custom_id" label="编号" width="160" />
          <el-table-column prop="name" label="名称" min-width="200" />
          <template #empty>暂无关联资产</template>
        </el-table>
      </el-tab-pane>

      <!-- 文件 -->
      <el-tab-pane label="文件" name="files" lazy>
        <EntityAttachments entity-type="part" :entity-id="id" :editable="canEdit" />
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
</style>
