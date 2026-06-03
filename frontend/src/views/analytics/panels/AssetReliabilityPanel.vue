<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { getAssetReliabilityAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import { listAssetCategories } from '@/api/assetCategories'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, AssetReliabilityAnalytics } from '@/types/analytics'
import type { AssetCategoryRead } from '@/types/maindata'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const data = ref<AssetReliabilityAnalytics | null>(null)
const loading = ref(false)
const categories = ref<AssetCategoryRead[]>([])
const categoryId = ref('')

const buildParams = (): AnalyticsParams => {
  const p = Object.fromEntries(
    Object.entries(props.baseParams).filter(([, v]) => v !== undefined),
  ) as AnalyticsParams
  if (categoryId.value) p.category_id = categoryId.value
  return p
}

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getAssetReliabilityAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  categories.value = await listAssetCategories()
})

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const pct = (n: number | null) => (n == null ? '—' : n.toFixed(1))
const hrs = (n: number | null) => (n == null ? '—' : n.toFixed(1))
const ratio = (n: number | null) => (n == null ? '—' : n.toFixed(3))

const availabilityOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  return {
    tooltip: {},
    xAxis: { type: 'category', data: d.assets.map((r) => r.name) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: d.assets.map((r) => r.availability_pct) }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('asset-reliability', buildParams())
  } catch {
    ElMessage.error('导出失败，请重试')
  }
}

defineExpose({ categoryId, fetch })
</script>

<template>
  <div class="panel" v-loading="loading">
    <div class="panel-toolbar">
      <el-select
        v-model="categoryId"
        clearable
        placeholder="资产分类"
        class="cat-select"
        @change="fetch"
      >
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button @click="onExport">导出CSV</el-button>
    </div>

    <el-row :gutter="12" class="kpi-row">
      <el-col :span="4">
        <KpiCard label="车队可用率" :value="pct(data?.fleet_availability_pct ?? null)" unit="%" />
      </el-col>
      <el-col :span="4">
        <KpiCard label="车队 MTTR" :value="hrs(data?.fleet_mttr_hours ?? null)" unit="h" />
      </el-col>
      <el-col :span="4">
        <KpiCard label="车队 MTBF" :value="hrs(data?.fleet_mtbf_hours ?? null)" unit="h" />
      </el-col>
      <el-col :span="4">
        <KpiCard
          label="总停机"
          :value="(data?.fleet_total_downtime_hours ?? 0).toFixed(1)"
          unit="h"
        />
      </el-col>
      <el-col :span="4">
        <KpiCard label="总维护成本" :value="data?.fleet_total_maintenance_cost ?? '—'" />
      </el-col>
    </el-row>

    <div class="chart-title">各资产可用率</div>
    <BaseChart :option="availabilityOption" />

    <div class="chart-title">资产可靠性明细</div>
    <el-table :data="data?.assets ?? []" border size="small">
      <el-table-column prop="custom_id" label="编号" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="可用率">
        <template #default="{ row }">{{ pct(row.availability_pct) }}%</template>
      </el-table-column>
      <el-table-column label="MTTR">
        <template #default="{ row }">{{ hrs(row.mttr_hours) }}</template>
      </el-table-column>
      <el-table-column label="MTBF">
        <template #default="{ row }">{{ hrs(row.mtbf_hours) }}</template>
      </el-table-column>
      <el-table-column prop="downtime_count" label="停机次数" />
      <el-table-column label="停机h">
        <template #default="{ row }">{{ row.total_downtime_hours.toFixed(1) }}</template>
      </el-table-column>
      <el-table-column prop="total_maintenance_cost" label="维护成本" />
      <el-table-column label="价值比">
        <template #default="{ row }">{{ ratio(row.cost_to_value_ratio) }}</template>
      </el-table-column>
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
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.cat-select {
  width: 180px;
}
.kpi-row {
  margin-bottom: 16px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  margin-top: 16px;
}
</style>
