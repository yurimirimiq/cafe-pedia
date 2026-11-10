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

// 서버가 준 사진 주소가 "/media/..." 처럼 상대 경로면 백엔드 주소를 붙인다
export const mediaUrl = (url) => (url?.startsWith('/') ? `${API_URL}${url}` : url)

// 모든 API 호출은 이 함수를 쓴다: 토큰을 붙이고, access 가 만료됐으면 한 번 새로 받아 다시 시도한다
export async function apiFetch(path, { method = 'GET', body } = {}) {
  const send = () =>
    fetch(`${API_URL}${path}`, {
      method,
      headers: {
        // 사진(FormData)은 브라우저가 Content-Type 을 직접 정한다
        ...(!(body instanceof FormData) && { 'Content-Type': 'application/json' }),
        ...(tokens.access && { Authorization: `Bearer ${tokens.access}` }),
      },
      body: body instanceof FormData ? body : body && JSON.stringify(body),
    })

  const hadToken = Boolean(tokens.access)
  let res = await send()
  if (res.status === 401 && tokens.refresh && (await refreshAccess())) res = await send()
  // 새 토큰도 못 받으면 로그인이 만료된 것: 토큰을 지우고 앱에 알린 뒤(auth.jsx 가 로그아웃 처리)
  // 토큰 없이 한 번 더 보낸다 — 깨진 토큰을 붙이면 로그인이 필요 없는 API 도 401 이 나기 때문
  if (res.status === 401 && hadToken) {
    tokens.clear()
    window.dispatchEvent(new Event('auth:expired'))
    res = await send()
  }

  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data
}

// 에러를 사람이 읽을 한 줄로: 서버가 준 이유 → 로그인 만료 → 서버 연결 실패 → fallback
export function errorText(err, fallback = '잠시 후 다시 시도하세요.') {
  if (!(err instanceof ApiError)) return '서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.'
  if (err.status === 401) return '로그인이 만료됐어요. 다시 로그인해 주세요.'
  const d = err.data
  if (d?.detail) return d.detail
  // DRF 검사 에러 {필드: [메시지]} (중첩될 수도 있음) 에서 글자만 모은다
  const msgs = d && typeof d === 'object' ? Object.values(d).flat(Infinity).filter((m) => typeof m === 'string') : []
  return msgs.length ? msgs.join(' ') : fallback
}
