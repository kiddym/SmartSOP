<script setup lang="ts">
interface Entry { label: string; to: string }
interface Stage { no: string; title: string; desc: string; entries: Entry[] }

const stages: Stage[] = [
  { no: '①', title: '组织基础', desc: '先决定启用哪些业务模块,再配组织与货币', entries: [
    { label: '公司设置 · 模块开关', to: '/admin/config/organization?tab=company' },
    { label: '货币', to: '/admin/currencies' },
  ]},
  { no: '②', title: '人员权限', desc: '角色 → 团队 → 用户,先有角色再分配', entries: [
    { label: '角色', to: '/admin/roles' },
    { label: '团队', to: '/admin/teams' },
    { label: '用户', to: '/admin/users' },
  ]},
  { no: '③', title: '全局参数', desc: '审批流、版本控制等全局开关,影响各模块行为', entries: [
    { label: '系统设置', to: '/admin/config/organization?tab=global' },
  ]},
  { no: '④', title: '业务模块', desc: '为已启用的模块配置字段、表单与分类', entries: [
    { label: 'SOP 配置', to: '/admin/config/sop' },
    { label: '工单配置', to: '/admin/config/work-order' },
    { label: '请求配置', to: '/admin/config/request' },
    { label: '自定义字段(资产/库存)', to: '/admin/config/custom-fields' },
  ]},
  { no: '⑤', title: '自动化', desc: '实体就绪后再配自动化规则', entries: [
    { label: '工作流', to: '/admin/workflows' },
  ]},
  { no: '⑥', title: '运维', desc: '数据导入、文件与审计', entries: [
    { label: '数据导入', to: '/admin/imports' },
    { label: '文件库', to: '/admin/files' },
    { label: '审计日志', to: '/admin/audit-logs' },
  ]},
]
</script>

<template>
  <div class="config-console">
    <h2 class="page-title">配置中心</h2>
    <p class="console-hint">初次部署建议从上往下依次配置;日常维护可直接点入对应模块。</p>
    <div class="stage-grid">
      <section v-for="s in stages" :key="s.no" class="stage-card">
        <header class="stage-head"><span class="stage-no">{{ s.no }}</span>{{ s.title }}</header>
        <p class="stage-desc">{{ s.desc }}</p>
        <ul class="stage-entries">
          <li v-for="e in s.entries" :key="e.to">
            <router-link :to="e.to">{{ e.label }}</router-link>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.config-console { padding: 20px 24px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0 0 6px; color: var(--text-primary); }
.console-hint { margin: 0 0 20px; color: var(--text-tertiary); font-size: 13px; }
.stage-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.stage-card { border: 1px solid var(--border-subtle); border-radius: 8px; padding: 16px; background: var(--bg-surface); }
.stage-head { font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
.stage-no { color: var(--accent); font-weight: 700; }
.stage-desc { margin: 8px 0 12px; font-size: 12px; color: var(--text-tertiary); }
.stage-entries { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.stage-entries a { color: var(--accent); text-decoration: none; font-size: 14px; }
.stage-entries a:hover { text-decoration: underline; }
</style>
