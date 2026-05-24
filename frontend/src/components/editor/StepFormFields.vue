<script setup lang="ts">
import { computed } from 'vue'
import type { InputSchema } from '@/types/node'

// 执行表单 12 型动态配置（§4.1 执行记录区 / Q261-Q262）。
const props = defineProps<{ schema: InputSchema; readonly?: boolean }>()
const emit = defineEmits<{ (e: 'update:schema', value: InputSchema): void }>()

const type = computed(() => props.schema.type)

function set(key: string, value: unknown): void {
  emit('update:schema', { ...props.schema, [key]: value })
}
function str(key: string): string {
  const v = props.schema[key]
  return typeof v === 'string' ? v : ''
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
function setOption(i: number, value: string): void {
  const list = [...options.value]
  list[i] = value
  set('options', list)
}
function addOption(): void {
  set('options', [...options.value, ''])
}
function removeOption(i: number): void {
  set(
    'options',
    options.value.filter((_, idx) => idx !== i),
  )
}
</script>

<template>
  <div class="form-fields">
    <template v-if="type === 'CHECK'">
      <el-form-item label="通过标签">
        <el-input :model-value="str('pass_label')" :disabled="readonly" @input="(v: string) => set('pass_label', v)" />
      </el-form-item>
      <el-form-item label="不通过标签">
        <el-input :model-value="str('fail_label')" :disabled="readonly" @input="(v: string) => set('fail_label', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'NUMBER'">
      <el-form-item label="单位">
        <el-input :model-value="str('unit')" :disabled="readonly" @input="(v: string) => set('unit', v)" />
      </el-form-item>
      <div class="num-row">
        <el-form-item label="最小值">
          <el-input-number :model-value="num('min')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('min', v)" />
        </el-form-item>
        <el-form-item label="最大值">
          <el-input-number :model-value="num('max')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max', v)" />
        </el-form-item>
        <el-form-item label="小数位">
          <el-input-number :model-value="num('decimals')" :min="0" :max="6" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('decimals', v)" />
        </el-form-item>
      </div>
    </template>

    <template v-else-if="type === 'METER'">
      <el-form-item label="仪表名称">
        <el-input :model-value="str('name')" :disabled="readonly" @input="(v: string) => set('name', v)" />
      </el-form-item>
      <el-form-item label="单位">
        <el-input :model-value="str('unit')" :disabled="readonly" @input="(v: string) => set('unit', v)" />
      </el-form-item>
      <div class="num-row">
        <el-form-item label="下限">
          <el-input-number :model-value="num('lower_limit')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('lower_limit', v)" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number :model-value="num('upper_limit')" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('upper_limit', v)" />
        </el-form-item>
        <el-form-item label="小数位">
          <el-input-number :model-value="num('decimals')" :min="0" :max="6" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('decimals', v)" />
        </el-form-item>
      </div>
    </template>

    <template v-else-if="type === 'CHECKBOX' || type === 'RADIO'">
      <el-form-item label="选项">
        <div class="opt-list">
          <div v-for="(opt, i) in options" :key="i" class="opt-row">
            <el-input :model-value="opt" :disabled="readonly" placeholder="选项文本" @input="(v: string) => setOption(i, v)" />
            <el-button v-if="!readonly" size="small" text @click="removeOption(i)">✕</el-button>
          </div>
          <el-button v-if="!readonly" size="small" @click="addOption">+ 添加选项</el-button>
        </div>
      </el-form-item>
    </template>

    <template v-else-if="type === 'UPLOAD'">
      <el-form-item label="接受类型 (accept)">
        <el-input :model-value="str('accept')" :disabled="readonly" placeholder="如 image/*,.pdf" @input="(v: string) => set('accept', v)" />
      </el-form-item>
      <el-form-item label="最大数量">
        <el-input-number :model-value="num('max_count')" :min="1" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max_count', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'YESNO'">
      <el-form-item label="是 标签">
        <el-input :model-value="str('yes_label')" :disabled="readonly" placeholder="是" @input="(v: string) => set('yes_label', v)" />
      </el-form-item>
      <el-form-item label="否 标签">
        <el-input :model-value="str('no_label')" :disabled="readonly" placeholder="否" @input="(v: string) => set('no_label', v)" />
      </el-form-item>
      <el-form-item label="包含『不适用』">
        <el-switch :model-value="bool('na_enabled')" :disabled="readonly" @change="(v: string | number | boolean) => set('na_enabled', !!v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'SIGNATURE'">
      <el-form-item label="签名提示">
        <el-input :model-value="str('hint')" :disabled="readonly" placeholder="如：操作人签名" @input="(v: string) => set('hint', v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'DATE'">
      <el-form-item label="包含时间">
        <el-switch :model-value="bool('with_time')" :disabled="readonly" @change="(v: string | number | boolean) => set('with_time', !!v)" />
      </el-form-item>
    </template>

    <template v-else-if="type === 'PHOTO'">
      <el-form-item label="最大张数">
        <el-input-number :model-value="num('max_count')" :min="1" :disabled="readonly" controls-position="right" @change="(v: number | undefined) => set('max_count', v)" />
      </el-form-item>
    </template>

    <el-text v-else type="info" size="small">该类型无需额外配置。</el-text>
  </div>
</template>

<style scoped>
.num-row {
  display: flex;
  gap: 12px;
}
.opt-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.opt-row {
  display: flex;
  gap: 6px;
  align-items: center;
}
</style>
