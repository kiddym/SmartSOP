<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import type { AssetMini, LocationMini } from '@/types/maindata'
import WorkOrdersPanel from './panels/WorkOrdersPanel.vue'
import CostsPanel from './panels/CostsPanel.vue'
import AssetReliabilityPanel from './panels/AssetReliabilityPanel.vue'
import InventoryPanel from './panels/InventoryPanel.vue'
import RequestsPanel from './panels/RequestsPanel.vue'
import PersonnelPanel from './panels/PersonnelPanel.vue'
import TrendsPanel from './panels/TrendsPanel.vue'

function defaultRange(): [string, string] {
  return [dayjs().subtract(90, 'day').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')]
}

const dateRange = ref<[string, string] | null>(defaultRange())
const assetId = ref('')
const locationId = ref('')
const activeTab = ref('work-orders')
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])

const baseParams = computed<Record<string, string | undefined>>(() => ({
  date_from: dateRange.value?.[0],
  date_to: dateRange.value?.[1],
  asset_id: assetId.value || undefined,
  location_id: locationId.value || undefined,
}))

onMounted(async () => {
  assetsMini.value = await listAssetsMini()
  locationsMini.value = await listLocationsMini()
})
</script>

<template>
  <div class="page">
    <div class="page-title">分析仪表盘</div>
    <div class="toolbar">
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
      />
      <el-select v-model="assetId" clearable filterable placeholder="资产" style="width: 180px">
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select v-model="locationId" clearable filterable placeholder="位置" style="width: 180px">
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="工单" name="work-orders" lazy>
        <WorkOrdersPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="成本" name="costs" lazy>
        <CostsPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="资产可靠性" name="asset-reliability" lazy>
        <AssetReliabilityPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="库存" name="inventory" lazy>
        <InventoryPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="请求" name="requests" lazy>
        <RequestsPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="人员" name="personnel" lazy>
        <PersonnelPanel :base-params="baseParams" />
      </el-tab-pane>
      <el-tab-pane label="趋势" name="trends" lazy>
        <TrendsPanel :base-params="baseParams" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 16px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
</style>
