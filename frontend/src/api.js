// 백엔드 주소. 배포할 때는 .env 의 VITE_API_URL 로 바꾼다
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// shortcut: 토큰을 localStorage 에 저장 — 간단하지만 XSS 에 약함. 서비스가 커지면 httpOnly 쿠키로 옮긴다
export const tokens = {
  get access() { return localStorage.getItem('access') },
  get refresh() { return localStorage.getItem('refresh') },
  save({ access, refresh }) {
    localStorage.setItem('access', access)
    if (refresh) localStorage.setItem('refresh', refresh)
  },
  clear() {
    localStorage.removeItem('access')
    localStorage.removeItem('refresh')
  },
}

// API 에러: status(예: 400)와 서버가 보낸 내용(data)을 함께 담는다
export class ApiError extends Error {
  constructor(status, data) {
    super(`API ${status}`)
    this.status = status
    this.data = data
  }
}

async function refreshAccess() {
  const res = await fetch(`${API_URL}/api/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: tokens.refresh }),
  })
  if (!res.ok) return false
  tokens.save(await res.json())
  return true
}

// 모든 API 호출은 이 함수를 쓴다: 토큰을 붙이고, access 가 만료됐으면 한 번 새로 받아 다시 시도한다
export async function apiFetch(path, { method = 'GET', body } = {}) {
  const send = () =>
    fetch(`${API_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(tokens.access && { Authorization: `Bearer ${tokens.access}` }),
      },
      body: body && JSON.stringify(body),
    })

  let res = await send()
  if (res.status === 401 && tokens.refresh && (await refreshAccess())) res = await send()

  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}
