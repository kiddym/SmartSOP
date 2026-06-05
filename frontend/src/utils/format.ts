import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

// 后端 ORM 时间戳序列化为「裸 UTC」（utcnow，无 Z/偏移），而 version_change_log 带显式 'Z'。
// 统一把无时区标记的字符串当作 UTC，再转本地，避免 dayjs 误按本地解析导致整体偏 8 小时。
const HAS_TZ = /[zZ]$|[+-]\d{2}:?\d{2}$/

function toLocal(value: string): dayjs.Dayjs {
  return HAS_TZ.test(value) ? dayjs(value) : dayjs.utc(value).local()
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  return toLocal(value).format('YYYY-MM-DD HH:mm')
}

export function formatDateTimeSeconds(value: string | null | undefined): string {
  if (!value) return '-'
  return toLocal(value).format('YYYY-MM-DD HH:mm:ss')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  return toLocal(value).format('YYYY-MM-DD')
}

export const LEVEL_OF_USE_LABELS: Record<string, string> = {
  reference: '参考',
  continuous: '连续使用',
  information: '信息',
}

/** 相对时间(自定义中文,无需 dayjs locale 配置;超 30 天显日期)。 */
export function relativeTime(value: string | null | undefined): string {
  if (!value) return ''
  const then = toLocal(value)
  const diffSec = dayjs().diff(then, 'second')
  if (diffSec < 60) return '刚刚'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 30) return `${diffDay} 天前`
  return formatDate(value)
}
