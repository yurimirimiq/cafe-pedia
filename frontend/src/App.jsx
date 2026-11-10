import { Component } from 'react'
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Calendar from './pages/Calendar'
import Collection from './pages/Collection'
import Collections from './pages/Collections'
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

// 화면을 그리다 코드 에러가 나도 흰 화면 대신 안내를 보여준다. 다른 페이지로 가면(key 가 바뀌면) 다시 그린다
class ErrorBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error) { console.error(error) }
  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="page notice">
        <h1>화면을 보여주지 못했어요</h1>
        <p className="muted">잠시 후 다시 시도하거나 홈으로 돌아가 주세요.</p>
        <div className="notice-btns">
          <button className="btn dark" onClick={() => window.location.reload()}>새로고침</button>
          <Link to="/" className="btn">홈으로</Link>
        </div>
      </div>
    )
  }
}

function NotFound() {
  return (
    <div className="page notice">
      <h1>없는 페이지예요</h1>
      <p className="muted">주소가 바뀌었거나 지워진 페이지일 수 있어요.</p>
      <div className="notice-btns"><Link to="/" className="btn dark">홈으로</Link></div>
    </div>
  )
}

// 탭 아이콘 (24px 선 아이콘). class "f" 인 부분은 지금 탭일 때 옅게 채운다
const ICONS = {
  home: <path className="f" d="M4 10.5 12 4l8 6.5V19.5a1.5 1.5 0 0 1-1.5 1.5H15v-5.5H9V21H5.5A1.5 1.5 0 0 1 4 19.5z" />,
  search: <><circle className="f" cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  near: <><path className="f" d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.3" /></>,
  calendar: <><rect className="f" x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" /></>,
  me: <><circle className="f" cx="12" cy="8.5" r="3.8" /><path className="f" d="M4.5 20.5c1.2-3.6 4.1-5.5 7.5-5.5s6.3 1.9 7.5 5.5z" /></>,
}

// 메뉴 한 칸: 넓은 화면에선 글자만, 폰에선 아이콘 (지금 탭만 글자까지 보이는 캡슐)
function Tab({ to, icon, label, end, className }) {
  return (
    <NavLink to={to} end={end} className={className}>
      <svg className="tab-icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS[icon]}</svg>
      <span className="tab-label">{label}</span>
    </NavLink>
  )
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
  const { user, ready, expired, dismissExpired, logout } = useAuth()
  const { pathname } = useLocation()
  // 저장된 토큰을 확인하는 동안 화면이 깜빡이지 않게 잠깐 기다린다
  if (!ready) return null

  return (
    <>
      <header className="nav">
        <Link to="/" className="logo">cafepedia</Link>
        <NavSearch />
        {/* 넓은 화면: 상단 메뉴 / 좁은 화면: CSS 로 화면 아래 떠 있는 탭 바가 된다 */}
        <nav className="menu">
          <Tab to="/" end icon="home" label="홈" />
          <Tab to="/search" icon="search" label="검색" className="mobile-only" />
          <Tab to="/nearby" icon="near" label="내 주변" />
          <Tab to="/calendar" icon="calendar" label="캘린더" />
          <Tab to="/me" icon="me" label="나의 기록" />
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
      {expired && pathname !== '/login' && (
        <div className="banner" role="alert">
          <span>로그인이 만료됐어요. 다시 로그인해 주세요.</span>
          <Link to="/login" className="btn dark small">로그인</Link>
          <button className="link small" onClick={dismissExpired} aria-label="안내 닫기">닫기</button>
        </div>
      )}
      <main>
        <ErrorBoundary key={pathname}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/nearby" element={<Nearby />} />
          <Route path="/ranking" element={<Ranking />} />
          <Route path="/collections" element={<Collections />} />
          <Route path="/collections/:id" element={<Collection />} />
          <Route path="/place/:id" element={<Place />} />
          <Route path="/users/:id" element={<UserProfile />} />
          <Route path="/calendar" element={<RequireAuth><Calendar /></RequireAuth>} />
          <Route path="/me" element={<RequireAuth><Me /></RequireAuth>} />
          <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/auth/kakao" element={<KakaoCallback />} />
          <Route path="/signup" element={user ? <Navigate to="/" replace /> : <Signup />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        </ErrorBoundary>
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
