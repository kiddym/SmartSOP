<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElTabs, ElTabPane } from 'element-plus'
import CompanySettingsView from '@/views/platform/CompanySettingsView.vue'
import SettingsView from '@/views/settings/SettingsView.vue'

// 公司资料(CompanySettingsView)+ 全局参数(SettingsView)合为一页两 tab。
// 两子页原样复用、各自带页标题,故本聚合页不再加标题。activeTab 由 ?tab= 派生
// (computed 保证前进/后退等路由变化时双向同步),供旧路由 redirect 落到指定 tab;
// 切换时写回 query。lazy 避免非激活子页初始即挂载、重复拉数据。
const route = useRoute()
const router = useRouter()
const activeTab = computed<string>(() => (route.query.tab as string) || 'company')
function onTabChange(t: string | number): void {
  router.replace({ query: { ...route.query, tab: String(t) } })
}
</script>

<template>
  <div class="config-aggregate">
    <el-tabs :model-value="activeTab" @update:model-value="onTabChange">
      <el-tab-pane label="公司资料" name="company" lazy><CompanySettingsView /></el-tab-pane>
      <el-tab-pane label="全局参数" name="global" lazy><SettingsView /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
</style>
