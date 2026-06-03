<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { getWorkOrderAnalytics, exportAnalytics } from '@/api/analytics'
import BaseChart from '@/components/analytics/BaseChart.vue'
import KpiCard from '@/components/analytics/KpiCard.vue'
import { listAssetsMini } from '@/api/assets'
import { listUsers } from '@/api/users'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import type { AnalyticsParams, WorkOrderAnalytics } from '@/types/analytics'
import type { AssetMini } from '@/types/maindata'
import type { UserRead } from '@/types/platform'

const props = defineProps<{ baseParams: Record<string, string | undefined> }>()

const WO_STATUS_LABELS: Record<string, string> = {
  OPEN: '待处理',
  IN_PROGRESS: '进行中',
  ON_HOLD: '挂起',
  COMPLETE: '已完成',
  CANCELED: '已取消',
}
const PRIORITY_LABELS: Record<string, string> = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高' }

const data = ref<WorkOrderAnalytics | null>(null)
const loading = ref(false)
const assetsMini = ref<AssetMini[]>([])
const users = ref<UserRead[]>([])

const buildParams = (): AnalyticsParams =>
  Object.fromEntries(
    Object.entries(props.baseParams).filter(([, v]) => v !== undefined),
  ) as AnalyticsParams

const fetch = async () => {
  loading.value = true
  try {
    data.value = await getWorkOrderAnalytics(buildParams())
  } catch {
    ElMessage.error('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  assetsMini.value = await listAssetsMini()
  users.value = await listUsers()
})

watch(() => props.baseParams, fetch, { immediate: true, deep: true })

const assetName = (id: string | null) => {
  if (!id) return '—'
  return assetsMini.value.find((a) => a.id === id)?.name ?? id
}
const userName = (id: string | null) => {
  if (!id) return '—'
  return users.value.find((u) => u.id === id)?.name ?? id
}

const pct = (n: number) => (n * 100).toFixed(1)
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
        data: Object.entries(d.by_status).map(([k, v]) => ({
          name: WO_STATUS_LABELS[k] ?? k,
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

const assetBarOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.by_asset.slice(0, 10)
  return {
    tooltip: {},
    xAxis: { type: 'category', data: rows.map((r) => assetName(r.asset_id)) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: rows.map((r) => r.count) }],
  }
})

const userBarOption = computed<EChartsOption>(() => {
  const d = data.value
  if (!d) return { series: [] }
  const rows = d.by_user.slice(0, 10)
  return {
    tooltip: {},
    xAxis: { type: 'category', data: rows.map((r) => userName(r.user_id)) },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: rows.map((r) => r.count) }],
  }
})

async function onExport() {
  try {
    await exportAnalytics('work-orders', buildParams())
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
      <el-col :span="4"><KpiCard label="总数" :value="data?.total ?? 0" /></el-col>
      <el-col :span="4">
        <KpiCard label="完成率" :value="data ? pct(data.completion_rate) : '—'" unit="%" />
      </el-col>
      <el-col :span="4"><KpiCard label="逾期" :value="data?.overdue ?? 0" /></el-col>
      <el-col :span="4">
        <KpiCard label="平均周期" :value="hrs(data?.avg_cycle_time_hours ?? null)" unit="h" />
      </el-col>
      <el-col :span="4">
        <KpiCard label="平均响应" :value="hrs(data?.avg_response_time_hours ?? null)" unit="h" />
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
        <div class="chart-title">资产工单量（前 10）</div>
        <BaseChart :option="assetBarOption" />
      </el-col>
      <el-col :span="12">
        <div class="chart-title">人员工单量（前 10）</div>
        <BaseChart :option="userBarOption" />
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
