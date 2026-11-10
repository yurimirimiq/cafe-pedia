import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Calendar from './pages/Calendar'
import Home from './pages/Home'
import KakaoCallback from './pages/KakaoCallback'
import Login from './pages/Login'
import Me from './pages/Me'
import Nearby from './pages/Nearby'
import Place from './pages/Place'
import Ranking from './pages/Ranking'
import Search from './pages/Search'
import Signup from './pages/Signup'
import UserProfile from './pages/UserProfile'

// 로그인해야 볼 수 있는 페이지: 로그인 안 했으면 로그인 화면으로 보낸다
function RequireAuth({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

// 상단 검색창: 엔터를 치면 검색 페이지로
function NavSearch() {
  const navigate = useNavigate()
  function onSubmit(e) {
    e.preventDefault()
    const q = e.target.q.value.trim()
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`)
  }
  return (
    <form className="nav-search" role="search" onSubmit={onSubmit}>
      <label className="sr-only" htmlFor="nav-q">검색어</label>
      <input id="nav-q" name="q" type="search" placeholder="어디 가고 싶어요? 카페, 식당, 동네" />
    </form>
  )
}

function Layout() {
  const { user, ready, logout } = useAuth()
  // 저장된 토큰을 확인하는 동안 화면이 깜빡이지 않게 잠깐 기다린다
  if (!ready) return null

  return (
    <>
      <header className="nav">
        <Link to="/" className="logo">cafepedia</Link>
        <NavSearch />
        {/* 넓은 화면: 상단 메뉴 / 좁은 화면: CSS 로 화면 아래 떠 있는 탭 바가 된다 */}
        <nav className="menu">
          <NavLink to="/" end>홈</NavLink>
          <NavLink to="/search" className="mobile-only">검색</NavLink>
          <NavLink to="/nearby">내 주변</NavLink>
          <NavLink to="/calendar">캘린더</NavLink>
          <NavLink to="/me">나의 기록</NavLink>
        </nav>
        <div className="nav-right">
          {user ? (
            <>
              <Link to="/me" className="avatar" title={`${user.nickname} (나의 기록)`}>{user.nickname[0]}</Link>
              <button className="link small" onClick={logout}>로그아웃</button>
            </>
          ) : (
            <>
              <Link to="/login" className="muted">로그인</Link>
              <Link to="/signup" className="btn dark small">회원가입</Link>
            </>
          )}
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/nearby" element={<Nearby />} />
          <Route path="/ranking" element={<Ranking />} />
          <Route path="/place/:id" element={<Place />} />
          <Route path="/users/:id" element={<UserProfile />} />
          <Route path="/calendar" element={<RequireAuth><Calendar /></RequireAuth>} />
          <Route path="/me" element={<RequireAuth><Me /></RequireAuth>} />
          <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/auth/kakao" element={<KakaoCallback />} />
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
