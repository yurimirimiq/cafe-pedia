import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import PlaceCard from '../components/PlaceCard'

const SHELVES = [
  ['recent', '최근 평가한 곳'],
  ['wishlist', '가고 싶어요'],
  ['feed', '팔로잉 소식'],
]
const EMPTY = {
  recent: '아직 평가한 곳이 없어요. ',
  wishlist: '가고 싶은 곳을 담아 보세요. ',
  feed: '한 줄 평의 닉네임을 눌러 마음에 드는 사람을 팔로우해 보세요. ',
}

export default function Me() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [shelf, setShelf] = useState('recent')

  useEffect(() => { apiFetch('/api/me/summary/').then(setData) }, [])
  if (!data) return <p className="page muted">불러오는 중…</p>

  const { counts, distribution, top_rating: top, taste } = data
  const max = Math.max(1, ...Object.values(distribution))
  const list = data[shelf]

  return (
    <section className="page me">
      <aside>
        <div className="avatar big">{user.nickname[0]}</div>
        <h1>{user.nickname}</h1>
        <p className="follow-counts">팔로워 <b>{counts.followers}</b> · 팔로잉 <b>{counts.following}</b></p>
        <Link to={`/collections?user=${user.id}`} className="btn small my-coll-link">내 컬렉션</Link>
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

        {taste && <Taste taste={taste} />}
      </aside>

      <div>
        <h2>보관함</h2>
        <div className="shelves">
          <div><b>카페</b><span className="muted small">{counts.cafe}곳 평가</span></div>
          <div><b>식당</b><span className="muted small">{counts.restaurant}곳 평가</span></div>
          <div><b>가고 싶어요</b><span className="muted small">{counts.wishes}곳</span></div>
        </div>

        <div className="seg shelf-tabs" role="group" aria-label="보관함">
          {SHELVES.map(([key, label]) => (
            <button key={key} aria-pressed={shelf === key} onClick={() => setShelf(key)}>{label}</button>
          ))}
        </div>
        {list.length ? (
          <div className="grid">
            {list.map((p, i) => (
              <PlaceCard key={`${p.id}-${i}`} place={p} rating={p.my_rating ?? p.rating} by={p.nickname} />
            ))}
          </div>
        ) : (
          <p className="muted">
            {EMPTY[shelf]}
            <Link to="/search" className="rating">검색하러 가기</Link>
          </p>
        )}
      </div>
    </section>
  )
}

// 내 취향 분석: 평균 별점(다른 사람과 비교), 자주 고른 키워드, 높게 준 종류, 자주 간 동네
function Taste({ taste }) {
  const mine = Number(taste.avg)
  const all = Number(taste.everyone_avg)
  const diff = mine - all
  const style = diff >= 0.3 ? '다른 사람보다 후하게 주는 편이에요' : diff <= -0.3 ? '다른 사람보다 깐깐하게 주는 편이에요' : '다른 사람들과 비슷하게 줘요'
  const pos = (v) => `${((v - 0.5) / 4.5) * 100}%` // 0.5 ~ 5.0 눈금 위치
  const names = (rows) => rows.map((r) => r.name).join(', ')
  return (
    <div className="taste">
      <h2>취향 분석</h2>
      <p className="lead">평균 {taste.avg}점을 줘요. {style}.</p>
      <div className="scale" role="img" aria-label={`내 평균 ${taste.avg}점, 전체 평균 ${taste.everyone_avg}점 (0.5~5.0)`}>
        <div className="bar" />
        <div className="span" style={{ left: pos(Math.min(mine, all)), width: `${(Math.abs(diff) / 4.5) * 100}%` }} />
        <div className="mark self" style={{ left: pos(mine) }}>나<b>{taste.avg}</b></div>
        <div className="mark all" style={{ left: pos(all) }}><b>{taste.everyone_avg}</b>전체 평균</div>
      </div>
      <div className="dist-axis muted small"><span>0.5</span><span>5.0</span></div>
      {taste.tags.length > 0 && (
        <ul className="tag-counts" aria-label="자주 고른 키워드">
          {taste.tags.map((t) => <li key={t.name}>{t.name}<em>{t.count}</em></li>)}
        </ul>
      )}
      <dl className="facts">
        {taste.details.length > 0 && <><dt>높게 준 종류</dt><dd>{names(taste.details)}</dd></>}
        {taste.areas.length > 0 && <><dt>자주 가는 동네</dt><dd>{names(taste.areas)}</dd></>}
      </dl>
    </div>
  )
}
