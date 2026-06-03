<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { getCostAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import { listAssetsMini } from '@/api/assets'
import { listVendorsMini } from '@/api/vendors'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, CostAnalytics } from '@/types/analytics'
import type { AssetMini } from '@/types/maindata'
import type { VendorMini } from '@/types/inventory'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const data = ref<CostAnalytics | null>(null)
const loading = ref(false)
const assetsMini = ref<AssetMini[]>([])
const vendorsMini = ref<VendorMini[]>([])

const buildParams = (): AnalyticsParams =>
  Object.fromEntries(
    Object.entries(props.baseParams).filter(([, v]) => v !== undefined),
  ) as AnalyticsParams

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getCostAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  ;[assetsMini.value, vendorsMini.value] = await Promise.all([listAssetsMini(), listVendorsMini()])
})

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const assetName = (id: string | null) => {
  if (!id) return '—'
  return assetsMini.value.find((a) => a.id === id)?.name ?? id
}

const vendorName = (id: string) => vendorsMini.value.find((v) => v.id === id)?.name ?? id

const maintCostByAssetOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.maintenance_cost_by_asset
  return {
    tooltip: {},
    legend: { data: ['备件', '人工', '额外'] },
    xAxis: { type: 'category', data: rows.map((r) => assetName(r.asset_id)) },
    yAxis: { type: 'value' },
    series: [
      { name: '备件', type: 'bar', stack: 'total', data: rows.map((r) => Number(r.parts_cost)) },
      { name: '人工', type: 'bar', stack: 'total', data: rows.map((r) => Number(r.labor_cost)) },
      {
        name: '额外',
        type: 'bar',
        stack: 'total',
        data: rows.map((r) => Number(r.additional_cost)),
      },
    ],
  }
})

const vendorSpendOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.po_spend_by_vendor
  return {
    tooltip: {},
    xAxis: { type: 'category', data: rows.map((r) => vendorName(r.vendor_id)) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: rows.map((r) => Number(r.spend)) }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('costs', buildParams())
  } catch {
    ElMessage.error('导出失败，请重试')
  }
}
</script>

<template>
  <div class="panel" v-loading="loading">
    <div class="panel-toolbar">
      <el-button @click="onExport">导出CSV</el-button>
    </div>

    <el-row :gutter="12" class="kpi-row">
      <el-col :span="4">
        <KpiCard label="总维护成本" :value="data?.total_maintenance_cost ?? '—'" />
      </el-col>
      <el-col :span="4">
        <KpiCard label="备件消耗" :value="data?.parts_consumption_cost ?? '—'" />
      </el-col>
      <el-col :span="4"><KpiCard label="人工" :value="data?.labor_cost ?? '—'" /></el-col>
      <el-col :span="4"><KpiCard label="额外" :value="data?.additional_cost ?? '—'" /></el-col>
      <el-col :span="4">
        <KpiCard label="采购承诺" :value="data?.po_spend_approved ?? '—'" />
      </el-col>
    </el-row>

    <el-row :gutter="12" class="chart-row">
      <el-col :span="12">
        <div class="chart-title">资产维护成本构成</div>
        <BaseChart :option="maintCostByAssetOption" />
      </el-col>
      <el-col :span="12">
        <div class="chart-title">供应商采购支出</div>
        <BaseChart :option="vendorSpendOption" />
      </el-col>
    </el-row>

    <div class="chart-title">备件消耗明细</div>
    <el-table :data="data?.consumption_by_part ?? []" border size="small">
      <el-table-column prop="custom_id" label="编号" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="qty" label="数量" />
      <el-table-column prop="cost" label="成本" />
    </el-table>
  </div>
</template>

<style scoped>
.panel {
  padding: 8px 0;
}
.panel-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
.kpi-row {
  margin-bottom: 16px;
}
.chart-row {
  margin-bottom: 16px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
