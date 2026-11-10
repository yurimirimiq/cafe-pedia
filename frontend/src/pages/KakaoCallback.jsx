import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import { useAuth } from '../auth'

// 카카오 로그인 후 돌아오는 페이지: ?code=...&state=... 를 서버에 보내 우리 토큰으로 바꾼다
export default function KakaoCallback() {
  const [params] = useSearchParams()
  const { loginWithTokens } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const sent = useRef(false) // 인가 코드는 한 번만 쓸 수 있어서, 개발 모드의 effect 두 번 실행을 막는다

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    const expected = sessionStorage.getItem('kakao_state')
    sessionStorage.removeItem('kakao_state')

    if (params.get('error')) return setError('카카오 로그인을 취소했어요.')
    if (!params.get('code') || !expected || params.get('state') !== expected) {
      return setError('로그인 요청이 올바르지 않아요. 처음부터 다시 시도해 주세요.')
    }
    apiFetch('/api/auth/kakao/', { method: 'POST', body: { code: params.get('code') } })
      .then(loginWithTokens)
      .then(() => navigate('/', { replace: true }))
      .catch((err) => setError(errorText(err, '카카오 로그인에 실패했어요.')))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="auth">
      {error ? (
        <>
          <p className="error" role="alert">{error}</p>
          <Link to="/login" className="btn">로그인 화면으로</Link>
        </>
      ) : (
        <p className="muted">카카오로 로그인하는 중…</p>
      )}
    </section>
  )
}
