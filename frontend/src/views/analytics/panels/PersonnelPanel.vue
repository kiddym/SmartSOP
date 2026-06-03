<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { getPersonnelAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, PersonnelAnalytics } from '@/types/analytics'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const data = ref<PersonnelAnalytics | null>(null)
const loading = ref(false)

const buildParams = (): AnalyticsParams => {
  const p: AnalyticsParams = {}
  if (props.baseParams.date_from) p.date_from = props.baseParams.date_from
  if (props.baseParams.date_to) p.date_to = props.baseParams.date_to
  return p
}

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getPersonnelAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const completedByUserOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.users
  return {
    tooltip: {},
    xAxis: { type: 'category', data: rows.map((u) => u.name ?? '—') },
    yAxis: { type: 'value' },
    series: [{ name: '完成数', type: 'bar', data: rows.map((u) => u.completed_count) }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('personnel', buildParams())
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

    <div class="chart-title">人员完成数</div>
    <BaseChart :option="completedByUserOption" />

    <div class="chart-title">人员明细</div>
    <el-table :data="data?.users ?? []" border size="small">
      <el-table-column label="姓名">
        <template #default="{ row }">{{ row.name ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="created_count" label="创建数" />
      <el-table-column prop="completed_count" label="完成数" />
      <el-table-column prop="assigned_count" label="被指派数" />
      <el-table-column label="工时">
        <template #default="{ row }">{{ row.labor_hours.toFixed(1) }}</template>
      </el-table-column>
      <el-table-column prop="labor_cost" label="工时成本" />
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
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  margin-top: 16px;
}
</style>
