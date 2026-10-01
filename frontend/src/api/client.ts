/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  // 带上当前登录人员工号，发苗等按点位授权的接口靠它裁决权限。
  let staffHeader: Record<string, string> = {}
  try {
    // 延迟引用，避免 store 与 api 模块互相 import 形成环。
    const raw = localStorage.getItem('planting-staff-id')
    if (raw) staffHeader = { 'X-Staff-Id': raw }
  } catch {
    /* localStorage 不可用时退化为未登录，后端按 0 处理 */
  }
  return fetch(url, {
    headers: { 'Content-Type': 'application/json', ...staffHeader, ...(init?.headers ?? {}) },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
