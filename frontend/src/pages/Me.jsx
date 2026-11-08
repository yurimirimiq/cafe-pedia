import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import PlaceCard from '../components/PlaceCard'

const SHELVES = [
  ['recent', '최근 평가한 곳'],
  ['wishlist', '가고 싶어요'],
]

export default function Me() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [shelf, setShelf] = useState('recent')

  useEffect(() => { apiFetch('/api/me/summary/').then(setData) }, [])
  if (!data) return <p className="page muted">불러오는 중…</p>

  const { counts, distribution, top_rating: top } = data
  const max = Math.max(1, ...Object.values(distribution))
  const list = data[shelf]

  return (
    <section className="page me">
      <aside>
        <div className="avatar big">{user.nickname[0]}</div>
        <h1>{user.nickname}</h1>
        <div className="counts">
          <div><b>{counts.reviews}</b><span>평가</span></div>
          <div><b>{counts.comments}</b><span>한 줄 평</span></div>
          <div><b>{counts.wishes}</b><span>가고 싶어요</span></div>
        </div>

        <h2>별점 분포 {top && <span className="muted small">가장 많이 준 별점 {top}</span>}</h2>
        <div className="dist" aria-label="별점 분포">
          {Object.entries(distribution).map(([r, n]) => (
            <div key={r} title={`${r}점 ${n}개`} className={r === top ? 'top' : ''} style={{ height: `${(n / max) * 100}%` }} />
          ))}
        </div>
        <div className="dist-axis muted small"><span>0.5</span><span>5.0</span></div>
      </aside>

      <div>
        <h2>보관함</h2>
        <div className="shelves">
          <div><b>카페</b><span className="muted small">{counts.cafe}곳 평가</span></div>
          <div><b>식당</b><span className="muted small">{counts.restaurant}곳 평가</span></div>
          <div><b>가고 싶어요</b><span className="muted small">{counts.wishes}곳</span></div>
        </div>

        <div className="chips" role="tablist">
          {SHELVES.map(([key, label]) => (
            <button key={key} role="tab" aria-selected={shelf === key} className={`chip${shelf === key ? ' on' : ''}`} onClick={() => setShelf(key)}>{label}</button>
          ))}
        </div>
        {list.length ? (
          <div className="grid">{list.map((p) => <PlaceCard key={p.id} place={p} rating={p.my_rating} />)}</div>
        ) : (
          <p className="muted">
            {shelf === 'recent' ? '아직 평가한 곳이 없어요. ' : '가고 싶은 곳을 담아 보세요. '}
            <Link to="/search" className="rating">검색하러 가기</Link>
          </p>
        )}
      </div>
    </section>
  )
}
