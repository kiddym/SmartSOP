<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { getRequestAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, RequestAnalytics } from '@/types/analytics'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const REQUEST_STATUS_LABELS: Record<string, string> = {
  PENDING: '待审批',
  APPROVED: '已批准',
  REJECTED: '已驳回',
  CANCELED: '已取消',
}
const PRIORITY_LABELS: Record<string, string> = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高' }

const data = ref<RequestAnalytics | null>(null)
const loading = ref(false)

const buildParams = (): AnalyticsParams =>
  Object.fromEntries(
    Object.entries(props.baseParams).filter(([, v]) => v !== undefined),
  ) as AnalyticsParams

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getRequestAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const hrs = (n: number | null) => (n == null ? '—' : n.toFixed(1))

const statusPieOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  return {
    tooltip: {},
    legend: {},
    series: [
      {
        type: 'pie',
        // 过滤 0 值切片：避免 0 值分类标签堆叠重叠、不可读。
        data: Object.entries(d.by_status)
          .filter(([, v]) => v > 0)
          .map(([k, v]) => ({
            name: REQUEST_STATUS_LABELS[k] ?? k,
            value: v,
          })),
      },
    ],
  }
})

const priorityBarOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  return {
    tooltip: {},
    xAxis: {
      type: 'category',
      data: Object.keys(d.by_priority).map((k) => PRIORITY_LABELS[k] ?? k),
    },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: Object.values(d.by_priority) }],
  }
})

const funnelBarOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  return {
    tooltip: {},
    xAxis: { type: 'category', data: ['收到', '解决', '转化'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [d.received, d.resolved, d.converted] }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('requests', buildParams())
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
      <el-col :span="6"><KpiCard label="总数" :value="data?.total ?? 0" /></el-col>
      <el-col :span="6"><KpiCard label="解决" :value="data?.resolved ?? 0" /></el-col>
      <el-col :span="6"><KpiCard label="转工单" :value="data?.converted ?? 0" /></el-col>
      <el-col :span="6">
        <KpiCard
          label="平均解决周期"
          :value="hrs(data?.avg_resolution_cycle_hours ?? null)"
          unit="h"
        />
      </el-col>
    </el-row>

    <el-row :gutter="12" class="chart-row">
      <el-col :span="12">
        <div class="chart-title">状态分布</div>
        <BaseChart :option="statusPieOption" />
      </el-col>
      <el-col :span="12">
        <div class="chart-title">优先级分布</div>
        <BaseChart :option="priorityBarOption" />
      </el-col>
    </el-row>

    <el-row :gutter="12" class="chart-row">
      <el-col :span="12">
        <div class="chart-title">处理漏斗（收到/解决/转化）</div>
        <BaseChart :option="funnelBarOption" />
      </el-col>
    </el-row>
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
