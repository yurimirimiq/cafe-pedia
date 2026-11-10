import { createContext, useContext, useEffect, useState } from 'react'
import { apiFetch, tokens } from './api'

// 로그인 상태를 앱 전체에서 꺼내 쓸 수 있게 Context 로 공유한다
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 처음 열 때 저장된 토큰으로 사용자를 확인하는 동안은 ready = false
  const [ready, setReady] = useState(!tokens.access)
  const [expired, setExpired] = useState(false) // 로그인 만료 안내를 띄울지

  useEffect(() => {
    // apiFetch 가 토큰 갱신에 실패하면 보내는 신호 → 로그아웃 상태로
    const onExpired = () => { setUser(null); setExpired(true) }
    window.addEventListener('auth:expired', onExpired)
    if (tokens.access) {
      // 만료(401)면 apiFetch 가 이미 토큰을 지웠다. 서버가 잠깐 꺼진 경우엔 토큰을 남겨 둔다
      apiFetch('/api/auth/me/')
        .then(setUser)
        .catch(() => {})
        .finally(() => setReady(true))
    }
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])

  async function login(username, password) {
    tokens.save(await apiFetch('/api/auth/login/', { method: 'POST', body: { username, password } }))
    setUser(await apiFetch('/api/auth/me/'))
    setExpired(false)
  }

  // 카카오 로그인처럼 서버가 토큰을 바로 준 경우
  async function loginWithTokens(newTokens) {
    tokens.save(newTokens)
    setUser(await apiFetch('/api/auth/me/'))
    setExpired(false)
  }

  async function signup(form) {
    await apiFetch('/api/auth/signup/', { method: 'POST', body: form })
    await login(form.username, form.password)
  }

  function logout() {
    tokens.clear()
    setUser(null)
    setExpired(false)
  }

  return <AuthContext.Provider value={{ user, ready, expired, dismissExpired: () => setExpired(false), login, loginWithTokens, signup, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
