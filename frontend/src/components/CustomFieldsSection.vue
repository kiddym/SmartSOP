<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { listCustomFields } from '@/api/customFields'
import type { CustomFieldDef, CustomFieldEntity } from '@/types/customField'

// ── props / emits ──────────────────────────────────────────
const props = withDefaults(
  defineProps<{
    entityType: CustomFieldEntity
    modelValue?: Record<string, unknown>
    readonly?: boolean
  }>(),
  {
    modelValue: () => ({}),
    readonly: false,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', val: Record<string, unknown>): void
}>()

// ── state ──────────────────────────────────────────────────
const defs = ref<CustomFieldDef[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchDefs() {
  try {
    defs.value = await listCustomFields(props.entityType)
  } catch {
    defs.value = []
  }
}

onMounted(fetchDefs)
watch(() => props.entityType, fetchDefs)

// ── value helpers ──────────────────────────────────────────
function getValue(key: string, fieldType: string): unknown {
  const v = props.modelValue[key]
  if (v !== undefined) return v
  if (fieldType === 'multi_select' || fieldType === 'checkbox') return []
  return null
}

function setValue(key: string, val: unknown) {
  emit('update:modelValue', { ...props.modelValue, [key]: val })
}

// ── readonly display helpers ───────────────────────────────
function displayValue(def: CustomFieldDef): string {
  const raw = props.modelValue[def.key]
  if (raw === undefined || raw === null || raw === '') return '—'

  if (def.field_type === 'multi_select' || def.field_type === 'checkbox') {
    const arr = Array.isArray(raw) ? raw : []
    if (!arr.length) return '—'
    return arr
      .map((v) => {
        const opt = def.options.find((o) => o.value === v)
        return opt ? (opt.label || opt.value) : String(v)
      })
      .join('、')
  }

  if (def.field_type === 'select') {
    const opt = def.options.find((o) => o.value === String(raw))
    return opt ? (opt.label || opt.value) : String(raw)
  }

  return String(raw)
}

// ── active options (filter out archived) ──────────────────
function activeOptions(def: CustomFieldDef) {
  return def.options.filter((o) => !o.archived)
}
</script>

<template>
  <div v-if="defs.length" class="custom-fields-section">
    <div class="section-title">自定义字段</div>

    <!-- readonly mode -->
    <template v-if="readonly">
      <div v-for="def in defs" :key="def.key" class="readonly-row">
        <span class="readonly-label">{{ def.name }}</span>
        <span class="readonly-value">{{ displayValue(def) }}</span>
      </div>
    </template>

    <!-- edit mode -->
    <template v-else>
      <el-form-item
        v-for="def in defs"
        :key="def.key"
        :label="def.name"
        :required="def.required"
      >
        <!-- text -->
        <el-input
          v-if="def.field_type === 'text'"
          :model-value="(getValue(def.key, def.field_type) as string) ?? ''"
          placeholder="请输入"
          @update:model-value="(v: string) => setValue(def.key, v)"
        />

        <!-- textarea -->
        <el-input
          v-else-if="def.field_type === 'textarea'"
          type="textarea"
          :model-value="(getValue(def.key, def.field_type) as string) ?? ''"
          placeholder="请输入"
          :rows="3"
          @update:model-value="(v: string) => setValue(def.key, v)"
        />

        <!-- number -->
        <el-input-number
          v-else-if="def.field_type === 'number'"
          :model-value="(getValue(def.key, def.field_type) as number | null) ?? undefined"
          controls-position="right"
          style="width: 100%"
          @update:model-value="(v: number) => setValue(def.key, v)"
        />

        <!-- date -->
        <el-date-picker
          v-else-if="def.field_type === 'date'"
          type="date"
          :model-value="(getValue(def.key, def.field_type) as string) ?? ''"
          value-format="YYYY-MM-DD"
          placeholder="请选择日期"
          style="width: 100%"
          @update:model-value="(v: string) => setValue(def.key, v)"
        />

        <!-- select (single) -->
        <el-select
          v-else-if="def.field_type === 'select'"
          :model-value="(getValue(def.key, def.field_type) as string) ?? ''"
          placeholder="请选择"
          clearable
          style="width: 100%"
          @update:model-value="(v: string) => setValue(def.key, v)"
        >
          <el-option
            v-for="opt in activeOptions(def)"
            :key="opt.value"
            :label="opt.label || opt.value"
            :value="opt.value"
          />
        </el-select>

        <!-- multi_select / checkbox (multiple select) -->
        <el-select
          v-else-if="def.field_type === 'multi_select' || def.field_type === 'checkbox'"
          :model-value="(getValue(def.key, def.field_type) as string[]) ?? []"
          multiple
          placeholder="请选择"
          clearable
          style="width: 100%"
          @update:model-value="(v: string[]) => setValue(def.key, v)"
        >
          <el-option
            v-for="opt in activeOptions(def)"
            :key="opt.value"
            :label="opt.label || opt.value"
            :value="opt.value"
          />
        </el-select>
      </el-form-item>
    </template>
  </div>
</template>

<style scoped>
.custom-fields-section {
  margin-top: 8px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.readonly-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 14px;
  line-height: 1.5;
}

.readonly-label {
  color: var(--el-text-color-secondary);
  min-width: 80px;
  flex-shrink: 0;
}

.readonly-value {
  color: var(--el-text-color-primary);
  word-break: break-word;
}
</style>
