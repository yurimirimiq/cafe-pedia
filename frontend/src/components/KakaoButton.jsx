import { useState } from 'react'
import { apiFetch } from '../api'

// "카카오로 시작하기": 카카오 로그인 화면으로 보냈다가 /auth/kakao 로 돌아온다
export default function KakaoButton() {
  const [error, setError] = useState('')

  async function start() {
    // 돌아왔을 때 같은 값인지 확인해서, 남이 만든 로그인 링크로 들어오는 것(CSRF)을 막는다
    const state = crypto.randomUUID().replaceAll('-', '')
    sessionStorage.setItem('kakao_state', state)
    try {
      const { url } = await apiFetch(`/api/auth/kakao/url/?state=${state}`)
      window.location.href = url
    } catch {
      setError('카카오 로그인을 시작하지 못했어요. 잠시 후 다시 시도하세요.')
    }
  }

  return (
    <>
      <button type="button" className="btn kakao" onClick={start}>
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3C6.48 3 2 6.48 2 10.78c0 2.78 1.86 5.22 4.66 6.6l-.95 3.48c-.08.3.26.54.52.37l4.15-2.74c.53.07 1.07.1 1.62.1 5.52 0 10-3.48 10-7.81S17.52 3 12 3z" /></svg>
        카카오로 시작하기
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </>
  )
}
