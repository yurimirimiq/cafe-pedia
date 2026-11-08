import { useAuth } from '../auth'

// 6단계에서 랭킹·포스터 줄로 채운다. 지금은 로그인 상태 확인용
export default function Home() {
  const { user } = useAuth()
  return (
    <section className="page">
      <h1>{user ? `${user.nickname}님, 오늘은 어디 다녀오셨어요?` : '다녀온 카페와 식당을 기록해 보세요'}</h1>
      <p className="muted">홈 화면은 6단계에서 만들어요.</p>
    </section>
  )
}
