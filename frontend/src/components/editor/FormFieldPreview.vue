<script setup lang="ts">
import { computed } from 'vue'
import type { InputSchema } from '@/types/node'

// 表单字段执行态只读预览（对标 DPMS StepInputDisplay）。按 schema.type 分发，纯展示无 emit。
const props = defineProps<{ schema: InputSchema }>()

const type = computed(() => props.schema.type)

function str(key: string, fallback = ''): string {
  const v = props.schema[key]
  return typeof v === 'string' && v !== '' ? v : fallback
}
function num(key: string): number | undefined {
  const v = props.schema[key]
  return typeof v === 'number' ? v : undefined
}
function bool(key: string): boolean {
  return props.schema[key] === true
}
const options = computed<string[]>(() => {
  const v = props.schema.options
  return Array.isArray(v) ? v.map((x) => String(x)) : []
})

const numberRange = computed(() => {
  const min = num('min')
  const max = num('max')
  const decimals = num('decimals')
  const parts: string[] = []
  if (min !== undefined || max !== undefined) parts.push(`范围 ${min ?? '-'} ~ ${max ?? '-'}`)
  if (decimals !== undefined) parts.push(`${decimals} 位小数`)
  return parts.join('，')
})
const meterRange = computed(() => {
  const lo = num('lower_limit')
  const hi = num('upper_limit')
  if (lo === undefined && hi === undefined) return ''
  return `下限 ${lo ?? '-'} / 上限 ${hi ?? '-'}`
})
</script>

<template>
  <div class="field-preview">
    <div class="fp-header">预览</div>
    <div class="fp-body">
      <div v-if="type === 'NUMBER'" class="fp-number">
        <el-input class="fp-input" disabled placeholder="数值">
          <template v-if="str('unit')" #append>{{ str('unit') }}</template>
        </el-input>
        <div v-if="numberRange" class="fp-hint">{{ numberRange }}</div>
      </div>

      <div v-else-if="type === 'METER'" class="fp-meter">
        <div class="fp-meter-name">{{ str('name', '仪表读数') }}</div>
        <el-input class="fp-input" disabled placeholder="读数">
          <template v-if="str('unit')" #append>{{ str('unit') }}</template>
        </el-input>
        <div v-if="meterRange" class="fp-hint fp-meter-range">{{ meterRange }}</div>
      </div>

      <div v-else-if="type === 'CHECK'" class="fp-buttons">
        <el-button disabled>{{ str('pass_label', '通过') }}</el-button>
        <el-button disabled>{{ str('fail_label', '不通过') }}</el-button>
      </div>

      <div v-else-if="type === 'YESNO'" class="fp-buttons">
        <el-button disabled>{{ str('yes_label', '是') }}</el-button>
        <el-button disabled>{{ str('no_label', '否') }}</el-button>
        <el-button v-if="bool('na_enabled')" disabled>不适用</el-button>
      </div>

      <div v-else-if="type === 'CHECKBOX'" class="fp-options">
        <template v-if="options.length">
          <el-checkbox v-for="(opt, i) in options" :key="i" disabled>{{ opt }}</el-checkbox>
        </template>
        <div v-else class="fp-hint">未配置选项</div>
      </div>

      <div v-else-if="type === 'RADIO'" class="fp-options">
        <template v-if="options.length">
          <el-radio v-for="(opt, i) in options" :key="i" :label="opt" disabled>{{ opt }}</el-radio>
        </template>
        <div v-else class="fp-hint">未配置选项</div>
      </div>

      <div v-else-if="type === 'UPLOAD'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加文件</div>
        <div class="fp-hint">接受 {{ str('accept', '*') }} · 最多 {{ num('max_count') ?? '不限' }}</div>
      </div>

      <div v-else-if="type === 'PHOTO'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加照片</div>
        <div class="fp-hint">最多 {{ num('max_count') ?? 1 }} 张</div>
      </div>

      <div v-else-if="type === 'SIGNATURE'" class="fp-placeholder">
        <div class="fp-ph-box">+ 添加签名</div>
        <div v-if="str('hint')" class="fp-hint">{{ str('hint') }}</div>
      </div>

      <div v-else-if="type === 'DATE'" class="fp-date">
        <el-input class="fp-input" disabled :placeholder="bool('with_time') ? '选择日期时间' : '选择日期'" />
      </div>

      <div v-else-if="type === 'COMMON'" class="fp-hint">通用操作说明型，执行时无独立录入控件。</div>

      <div v-else class="fp-hint">该步骤无需填写录入项。</div>
    </div>
  </div>
</template>

<style scoped>
.field-preview {
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  overflow: hidden;
}
.fp-header {
  padding: 6px 10px;
  background: var(--el-fill-color-light, #f5f7fa);
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
.fp-body {
  padding: 10px;
}
.fp-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
  margin-top: 6px;
}
.fp-input {
  max-width: 240px;
}
.fp-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.fp-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fp-meter-name {
  font-size: 13px;
  margin-bottom: 4px;
}
.fp-meter-range {
  color: var(--el-color-warning, #e6a23c);
}
.fp-ph-box {
  border: 1px dashed var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  padding: 16px;
  text-align: center;
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
}
</style>
