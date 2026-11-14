import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import { useAuth } from '../auth'
import CollectionCard from '../components/CollectionCard'
import PlaceCard from '../components/PlaceCard'
import { getCoords, meters } from '../location'
import { loadRecent } from '../recent'
import { keywords } from '../components/PlaceCard'
import Poster from '../components/Poster'

const CATEGORIES = [
  ['', '전체'],
  ['FD6', '밥'],
  ['CE7', '카페'],
  ['BAR', '술'],
]

export default function Search() {
  // 검색어·분류를 주소(?q=...&category=...)에 담아 두면 뒤로 가기·새로고침해도 결과가 유지된다
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const [input, setInput] = useState(q)
  const [state, setState] = useState({ status: 'idle', places: [] })
  // 위치는 주소에 남기지 않는다 (방문 기록·공유 링크에 좌표가 남지 않게)
  const [coords, setCoords] = useState(null)
  const [locating, setLocating] = useState(false)
  const [locError, setLocError] = useState('')

  // 같은 조건의 검색인지 구분하는 값: "더 보기"가 늦게 와도 다른 검색 결과에 붙지 않게
  const key = `${q}|${category}|${coords?.lat},${coords?.lng}`
  const searchUrl = (page) => `/api/places/search/?${new URLSearchParams({ q, page, ...(category && { category }), ...coords })}`
  const failText = (err) => errorText(err, '검색하지 못했어요. 잠시 후 다시 시도하세요.')

  useEffect(() => {
    if (!q) return setState({ status: 'idle', places: [] })
    let ignore = false // 검색어를 빨리 바꿨을 때 늦게 온 이전 결과를 무시
    setState((s) => ({ ...s, status: 'loading' }))
    apiFetch(searchUrl(1))
      .then((res) => !ignore && setState({ status: 'done', key, places: res.places, page: 1, hasMore: res.has_more }))
      .catch((err) => !ignore && setState({ status: 'error', places: [], message: failText(err) }))
    return () => { ignore = true }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  // 카카오는 15개씩 3페이지(45곳)까지 준다. 이미 받은 장소는 빼고 이어 붙인다
  async function loadMore() {
    setState((s) => ({ ...s, status: 'more', moreError: '' }))
    const page = state.page + 1
    try {
      const res = await apiFetch(searchUrl(page))
      setState((s) => {
        if (s.key !== key) return s
        const ids = new Set(s.places.map((p) => p.id))
        return { ...s, status: 'done', places: [...s.places, ...res.places.filter((p) => !ids.has(p.id))], page, hasMore: res.has_more }
      })
    } catch (err) {
      setState((s) => (s.key === key ? { ...s, status: 'done', moreError: failText(err) } : s))
    }
  }

  function toggleNear() {
    setLocError('')
    if (coords) return setCoords(null)
    setLocating(true)
    getCoords().then(setCoords, (err) => setLocError(err.message)).finally(() => setLocating(false))
  }

  function onSubmit(e) {
    e.preventDefault()
    const next = input.trim()
    if (next) setParams({ q: next, ...(category && { category }) })
  }

  const setCategory = (c) => setParams({ ...(q && { q }), ...(c && { category: c }) })

  return (
    <section className="page search">
      <form onSubmit={onSubmit} role="search">
        <label className="search-box">
          <span className="sr-only">검색어</span>
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="카페, 식당, 술집, 동네 검색 (예: 망원동 국밥)"
            autoFocus
          />
          <button className="btn primary">검색</button>
        </label>
      </form>

      <div className="filters">
        <div className="chips" role="group" aria-label="분류">
          {CATEGORIES.map(([code, label]) => (
            <button key={code} className={`chip${category === code ? ' on' : ''}`} aria-pressed={category === code} onClick={() => setCategory(code)}>
              {label}
            </button>
          ))}
        </div>
        <div className="chips">
          <button className={`chip${coords ? ' on' : ''}`} aria-pressed={Boolean(coords)} onClick={toggleNear} disabled={locating}>
            {locating ? '위치 찾는 중…' : '내 위치 가까운 순'}
          </button>
        </div>
      </div>
      {locError && <p className="error" role="alert">{locError}</p>}

      {state.status === 'idle' && (
        <>
          <p className="muted">가게 이름이나 "동네 + 메뉴"로 찾아보세요.</p>
          <RecentPlaces category={category} />
          <Recommendations category={category} />
        </>
      )}
      {state.status === 'loading' && <p className="muted">찾는 중…</p>}
      {state.status === 'error' && <p className="error" role="alert">{state.message}</p>}
      {state.status === 'done' && state.places.length === 0 && (
        <p className="muted">"{q}"에 맞는 카페·식당·술집이 없어요. 동네 이름을 붙여서 다시 찾아보세요.</p>
      )}

      {state.places.length > 0 && (
        <ul className="results" aria-busy={state.status === 'loading'}>
          {state.places.map((p) => (
            <li key={p.id}>
              <Link to={`/place/${p.id}`} className="result">
                <Poster place={p} className="list-photo" />
                <div className="result-body">
                  <strong>{p.name}</strong>
                  <span className="muted">{p.distance != null && `${meters(p.distance)} · `}{[p.category_label, ...keywords(p, 2)].filter((v, i, a) => a.indexOf(v) === i).join(' · ')}</span>
                  <span className="muted small">{p.address}</span>
                </div>
                {p.review_count ? <span className="rating">{p.avg_rating}</span> : <span className="muted small">평가 없음</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {state.moreError && <p className="error" role="alert">{state.moreError}</p>}
      {state.hasMore && state.status !== 'loading' && (
        <button className="btn wide more-btn" onClick={loadMore} disabled={state.status === 'more'}>
          {state.status === 'more' ? '불러오는 중…' : '검색 결과 더 보기'}
        </button>
      )}
      {q && <SearchCollections q={q} />}
      <p className="muted small credit">장소 정보 출처: 카카오</p>
    </section>
  )
}

// 최근 본 장소 (이 브라우저에 저장된 것)
function RecentPlaces({ category }) {
  const list = loadRecent().filter((p) => !category || p.category === category).slice(0, 6)
  if (!list.length) return null
  return (
    <>
      <h2 className="sec-title">최근 본 장소</h2>
      <div className="recent-row">
        {list.map((p) => (
          <Link key={p.id} to={`/place/${p.id}`}>
            <Poster place={p} className="recent-photo" />
            <span>{p.name}<small>{p.category_detail.split(' > ').at(-1)}</small></span>
          </Link>
        ))}
      </div>
    </>
  )
}

// 좋아할 만한 곳: 취향이 비슷한 사람들의 별점으로 계산한 예상 별점 순 (로그인했을 때만)
function Recommendations({ category }) {
  const { user } = useAuth()
  const [list, setList] = useState(null)

  useEffect(() => {
    if (!user) return
    apiFetch(`/api/recommendations/${category ? `?category=${category}` : ''}`).then(setList).catch(() => setList([]))
  }, [user, category])

  if (!user || !list?.length) return null
  const guessed = list.some((p) => p.predicted_rating)
  return (
    <>
      <div className="sec-title-row">
        <div>
          <h2 className="sec-title">좋아할 만한 곳</h2>
          <p className="muted small">
            {guessed ? '나와 별점 패턴이 비슷한 사람들이 높게 준 곳이에요.' : '평가를 5개 넘게 남기면 취향이 비슷한 사람들을 찾아 예상 별점을 알려드려요.'}
          </p>
        </div>
        {guessed && (
          <p className="legend"><i className="hollow">4.3</i>내 예상 별점<i>4.3</i>내가 준 별점</p>
        )}
      </div>
      <div className="grid">
        {list.map((p) => <PlaceCard key={p.id} place={p} predicted={p.predicted_rating ?? undefined} />)}
      </div>
    </>
  )
}

// 검색어가 제목·소개에 들어간 컬렉션 (예: "카공" → 카공하기 좋은 카페)
function SearchCollections({ q }) {
  const [list, setList] = useState([])
  useEffect(() => {
    let ignore = false
    apiFetch(`/api/collections/?${new URLSearchParams({ q, sort: 'popular' })}`)
      .then((rows) => !ignore && setList(rows))
      .catch(() => !ignore && setList([]))
    return () => { ignore = true }
  }, [q])
  if (!list.length) return null
  return (
    <>
      <h2 className="sec-title">"{q}" 컬렉션</h2>
      <div className="coll-grid">{list.slice(0, 4).map((c) => <CollectionCard key={c.id} collection={c} />)}</div>
    </>
  )
}
