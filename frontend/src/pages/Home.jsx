import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import CollectionCard from '../components/CollectionCard'
import PlaceCard from '../components/PlaceCard'
import Poster from '../components/Poster'

// 홈 맨 위 탭 (왓챠피디아의 홈 | 영화 | 책 처럼): 홈은 전체, 나머지는 그 분류만. 고른 탭은 주소(?category=)에 담는다
const KINDS = [
  ['', '홈', <>밥 먹고,<br />카페 가고,<br />술 한잔하고.</>],
  ['FD6', '밥', <>오늘은<br />어디서<br />밥 먹지.</>],
  ['CE7', '카페', <>오늘은<br />어느 카페<br />가지.</>],
  ['BAR', '술', <>오늘은<br />어디서<br />한잔하지.</>],
]
const short = (area) => area.replace(/동$/, '') // "성수동" → "성수"

export default function Home() {
  const [params] = useSearchParams()
  const kind = KINDS.find(([code]) => code === params.get('category')) ?? KINDS[0] // 모르는 값이면 홈
  const category = kind[0]
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [areaName, setAreaName] = useState(null)

  useEffect(() => {
    // 탭을 빠르게 바꾸면 먼저 누른 탭의 응답이 늦게 와서 지금 탭을 덮을 수 있어, 지난 요청의 응답은 버린다
    let stale = false
    setError('')
    apiFetch(`/api/home/${category ? `?category=${category}` : ''}`)
      .then((d) => stale || setData(d))
      .catch((err) => stale || setError(errorText(err)))
    return () => { stale = true }
  }, [category])

  const area = data?.areas.find((a) => a.name === areaName) ?? data?.areas[0]
  // 큰 사진 자리: 고른 동네에서 별점이 가장 높은 곳, 아직 아무도 평가 안 했으면 카카오 검색 첫 번째
  const hero = area && ([...area.places].filter((p) => p.avg_rating).sort((a, b) => b.avg_rating - a.avg_rating)[0] ?? area.places[0])
  const word = { FD6: '맛집', BAR: '술집' }[category] ?? '카페'

  return (
    <div className="home">
      <nav className="kinds" aria-label="분류">
        {KINDS.map(([code, label]) => (
          <Link key={code} to={code ? `/?category=${code}` : '/'} aria-current={code === category ? 'page' : undefined}>{label}</Link>
        ))}
      </nav>
      <section className="hero">
        <div>
          <h1>{kind[2]}</h1>
          <p>
            다녀온 카페·식당·술집에 별점을 남기면
            <br />
            {data?.total_reviews ? `지금까지 ${data.total_reviews.toLocaleString()}개의 별점이 쌓였어요.` : '취향이 비슷한 사람들의 단골집이 보여요.'}
          </p>
          {data && (
            <div className="pills" role="tablist" aria-label="동네">
              {data.areas.map((a) => (
                <button key={a.name} role="tab" aria-selected={a === area} onClick={() => setAreaName(a.name)}>
                  {short(a.name)}
                </button>
              ))}
            </div>
          )}
        </div>
        {hero && (
          <Link to={`/place/${hero.id}`} className="hero-card">
            <Poster place={hero} className="hero-photo">
              {hero.avg_rating && <span className="score">{hero.avg_rating}</span>}
              <span className="who">
                <strong>{hero.name}</strong>
                <span>{hero.review_count ? `카페피디아 평가 ${hero.review_count}개` : `요즘 ${short(area.name)}에서 많이 찾는 ${word}`}</span>
              </span>
            </Poster>
          </Link>
        )}
      </section>

      {error && <p className="error page" role="alert">불러오지 못했어요. {error}</p>}

      {data && (
        <section className="sec" id="ranking">
          <div className="sec-head">
            <h2>카페피디아 별점 랭킹</h2>
            {data.ranking.length > 0 && <Link to={`/ranking${category ? `?category=${category}` : ''}`} className="more">키워드·동네별 랭킹 보기</Link>}
          </div>
          {data.ranking.length > 0 ? (
            <div className="cards fit">{data.ranking.slice(0, 8).map((p, i) => <PlaceCard key={p.id} place={p} rank={i + 1} />)}</div>
          ) : (
            <p className="muted empty">
              아직 평가가 없어요. 다녀온 곳을 찾아 첫 별점을 남겨 보세요. <Link to="/search" className="rating">검색하러 가기</Link>
            </p>
          )}
        </section>
      )}

      {area && (
        <section className="sec">
          <div className="sec-head">
            <h2>요즘 {short(area.name)}에서 많이 가는 {word}</h2>
          </div>
          <div className="cards fit">{area.places.slice(0, 8).map((p) => <PlaceCard key={p.id} place={p} />)}</div>
          <Link to={`/search?q=${area.name} ${word}`} className="more">{short(area.name)} {word} 더 보기</Link>
          <p className="muted small credit">동네별 목록은 카카오 장소 검색 결과 순서예요.</p>
        </section>
      )}

      <PopularCollections />

      {data?.recent.length > 0 && (
        <section className="sec">
          <div className="sec-head"><h2>방금 별점이 남겨진 곳</h2></div>
          <div className="cards fit">{data.recent.slice(0, 4).map((p) => <PlaceCard key={p.id} place={p} />)}</div>
        </section>
      )}
    </div>
  )
}

// 사람들이 만든 컬렉션 (좋아요 많은 순 3개)
function PopularCollections() {
  const [list, setList] = useState([])
  useEffect(() => { apiFetch('/api/collections/?sort=popular').then(setList).catch(() => {}) }, [])
  if (!list.length) return null
  return (
    <section className="sec">
      <div className="sec-head">
        <h2>사람들이 만든 컬렉션</h2>
        <Link to="/collections" className="more">컬렉션 더 보기</Link>
      </div>
      <div className="coll-grid">{list.slice(0, 3).map((c) => <CollectionCard key={c.id} collection={c} />)}</div>
    </section>
  )
}
