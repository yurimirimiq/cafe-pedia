import { useEffect, useState } from 'react'
import { API_URL } from './api'

// 1단계 확인용 화면: 백엔드 /api/hello/ 응답을 보여준다
export default function App() {
  const [message, setMessage] = useState('백엔드에 연결하는 중…')

  useEffect(() => {
    fetch(`${API_URL}/api/hello/`)
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage('백엔드에 연결하지 못했어요. 백엔드 서버가 켜져 있는지 확인하세요.'))
  }, [])

  return (
    <main style={{ padding: '48px 40px' }}>
      <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700, color: 'var(--brown)', letterSpacing: '-0.03em' }}>
        cafepedia
      </h1>
      <p style={{ color: 'var(--mute)' }}>{message}</p>
    </main>
  )
}
