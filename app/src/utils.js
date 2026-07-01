export const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export function idxToLabel(idx) {
  return `${MONTH_NAMES[idx % 12]} ${2000 + Math.floor(idx / 12)}`
}

export function parseMonthInput(str) {
  const m = str.match(/^(\d{1,2})\/(\d{4})$/)
  if (!m) return null
  const mo = parseInt(m[1], 10)
  const yr = parseInt(m[2], 10)
  if (mo < 1 || mo > 12 || yr < 2000 || yr > 2026) return null
  return (yr - 2000) * 12 + (mo - 1)
}
