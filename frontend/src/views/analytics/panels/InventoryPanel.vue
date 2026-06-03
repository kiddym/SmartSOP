<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { getInventoryAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import { listPartCategories } from '@/api/partCategories'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, InventoryAnalytics } from '@/types/analytics'
import type { PartCategoryRead } from '@/types/inventory'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const data = ref<InventoryAnalytics | null>(null)
const loading = ref(false)
const categories = ref<PartCategoryRead[]>([])
const categoryId = ref('')

const buildParams = (): AnalyticsParams => {
  const p: AnalyticsParams = {}
  if (props.baseParams.date_from) p.date_from = props.baseParams.date_from
  if (props.baseParams.date_to) p.date_to = props.baseParams.date_to
  if (categoryId.value) p.category_id = categoryId.value
  return p
}

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getInventoryAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  categories.value = await listPartCategories()
})

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const abcParetoOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.abc_classification
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['消耗价值', '累计占比'] },
    xAxis: { type: 'category', data: rows.map((r) => r.name) },
    yAxis: [
      { type: 'value', name: '消耗价值' },
      { type: 'value', name: '累计%', max: 100, axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      {
        name: '消耗价值',
        type: 'bar',
        yAxisIndex: 0,
        data: rows.map((r) => Number(r.consumption_value)),
      },
      {
        name: '累计占比',
        type: 'line',
        yAxisIndex: 1,
        data: rows.map((r) => r.cumulative_pct),
      },
    ],
  }
})

const categoryPieOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  return {
    tooltip: {},
    legend: {},
    series: [
      {
        type: 'pie',
        data: d.inventory_value_by_category.map((r) => ({
          name: r.name ?? '未分类',
          value: Number(r.value),
        })),
      },
    ],
  }
})

const topConsumedOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.top_consumed_parts
  return {
    tooltip: {},
    xAxis: { type: 'category', data: rows.map((r) => r.name) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: rows.map((r) => Number(r.qty)) }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('inventory', buildParams())
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
        placeholder="备件分类"
        class="cat-select"
        @change="fetch"
      >
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button @click="onExport">导出CSV</el-button>
    </div>

    <el-row :gutter="12" class="kpi-row">
      <el-col :span="6">
        <KpiCard label="库存总值" :value="data?.total_inventory_value ?? '—'" />
      </el-col>
      <el-col :span="6">
        <KpiCard label="低库存数" :value="data?.low_stock_count ?? 0" />
      </el-col>
      <el-col :span="6">
        <KpiCard label="A类数" :value="data?.abc_summary?.A ?? 0" />
      </el-col>
    </el-row>

    <div class="chart-title">ABC 帕累托分析</div>
    <BaseChart :option="abcParetoOption" />

    <el-row :gutter="12" class="chart-row">
      <el-col :span="12">
        <div class="chart-title">分类库存价值</div>
        <BaseChart :option="categoryPieOption" />
      </el-col>
      <el-col :span="12">
        <div class="chart-title">消耗量前列备件</div>
        <BaseChart :option="topConsumedOption" />
      </el-col>
    </el-row>

    <div class="chart-title">低库存明细</div>
    <el-table :data="data?.low_stock_items ?? []" border size="small">
      <el-table-column prop="custom_id" label="编号" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="quantity" label="库存" />
      <el-table-column prop="min_quantity" label="最低" />
      <el-table-column prop="shortfall" label="缺口" />
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
.chart-row {
  margin-bottom: 16px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  margin-top: 16px;
}
</style>
