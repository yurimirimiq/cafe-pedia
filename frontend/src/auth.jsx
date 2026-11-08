import { createContext, useContext, useEffect, useState } from 'react'
import { apiFetch, tokens } from './api'

// 로그인 상태를 앱 전체에서 꺼내 쓸 수 있게 Context 로 공유한다
const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 처음 열 때 저장된 토큰으로 사용자를 확인하는 동안은 ready = false
  const [ready, setReady] = useState(!tokens.access)

  useEffect(() => {
    if (!tokens.access) return
    apiFetch('/api/auth/me/')
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setReady(true))
  }, [])

  async function login(username, password) {
    tokens.save(await apiFetch('/api/auth/login/', { method: 'POST', body: { username, password } }))
    setUser(await apiFetch('/api/auth/me/'))
  }

  async function signup(form) {
    await apiFetch('/api/auth/signup/', { method: 'POST', body: form })
    await login(form.username, form.password)
  }

  function logout() {
    tokens.clear()
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, ready, login, signup, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
