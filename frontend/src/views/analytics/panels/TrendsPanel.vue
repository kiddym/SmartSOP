<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { getTrendAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, TrendAnalytics } from '@/types/analytics'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const data = ref<TrendAnalytics | null>(null)
const loading = ref(false)
const granularity = ref<'day' | 'week'>('day')

const buildParams = (): AnalyticsParams => {
  const p: AnalyticsParams = { granularity: granularity.value }
  if (props.baseParams.date_from) p.date_from = props.baseParams.date_from
  if (props.baseParams.date_to) p.date_to = props.baseParams.date_to
  return p
}

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getTrendAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const trendOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const x = d.buckets.map((b) => b.bucket_start)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['工单创建', '工单完成', '请求收到', '请求解决'] },
    xAxis: { type: 'category', data: x },
    yAxis: { type: 'value' },
    series: [
      { name: '工单创建', type: 'line', data: d.buckets.map((b) => b.work_orders_created) },
      { name: '工单完成', type: 'line', data: d.buckets.map((b) => b.work_orders_completed) },
      { name: '请求收到', type: 'line', data: d.buckets.map((b) => b.requests_received) },
      { name: '请求解决', type: 'line', data: d.buckets.map((b) => b.requests_resolved) },
    ],
  }
})

async function onExport() {
  try {
    await exportAnalytics('trends', buildParams())
  } catch {
    ElMessage.error('导出失败，请重试')
  }
}

defineExpose({ granularity, fetch })
</script>

<template>
  <div class="panel" v-loading="loading">
    <div class="panel-toolbar">
      <el-radio-group v-model="granularity" @change="fetch">
        <el-radio-button :value="'day'">日</el-radio-button>
        <el-radio-button :value="'week'">周</el-radio-button>
      </el-radio-group>
      <el-button @click="onExport">导出CSV</el-button>
    </div>

    <div class="chart-title">工单与请求趋势</div>
    <BaseChart :option="trendOption" height="400px" />
  </div>
</template>

<style scoped>
.panel {
  padding: 8px 0;
}
.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}
</style>
