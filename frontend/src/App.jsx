import { BrowserRouter, Link, Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Home from './pages/Home'
import Login from './pages/Login'
import Signup from './pages/Signup'

const Soon = ({ title }) => (
  <section className="page">
    <h1>{title}</h1>
    <p className="muted">곧 만들어요.</p>
  </section>
)

// 로그인해야 볼 수 있는 페이지: 로그인 안 했으면 로그인 화면으로 보낸다
function RequireAuth({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function Layout() {
  const { user, ready, logout } = useAuth()
  // 저장된 토큰을 확인하는 동안 화면이 깜빡이지 않게 잠깐 기다린다
  if (!ready) return null

  return (
    <>
      <header className="nav">
        <Link to="/" className="logo">cafepedia</Link>
        <nav>
          <NavLink to="/" end>홈</NavLink>
          <NavLink to="/search">검색</NavLink>
          <NavLink to="/calendar">캘린더</NavLink>
          <NavLink to="/me">나의 기록</NavLink>
        </nav>
        <div className="nav-right">
          {user ? (
            <>
              <span className="avatar" title={user.nickname}>{user.nickname[0]}</span>
              <button className="link" onClick={logout}>로그아웃</button>
            </>
          ) : (
            <>
              <Link to="/login" className="muted">로그인</Link>
              <Link to="/signup" className="btn primary small">회원가입</Link>
            </>
          )}
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Soon title="검색" />} />
          <Route path="/calendar" element={<RequireAuth><Soon title="캘린더" /></RequireAuth>} />
          <Route path="/me" element={<RequireAuth><Soon title="나의 기록" /></RequireAuth>} />
          <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/signup" element={user ? <Navigate to="/" replace /> : <Signup />} />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout />
      </AuthProvider>
    </BrowserRouter>
  )
}
