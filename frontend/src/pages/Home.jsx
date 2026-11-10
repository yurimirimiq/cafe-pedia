import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import PlaceCard from '../components/PlaceCard'
import Poster from '../components/Poster'

const KINDS = [
  ['', '카페'],
  ['FD6', '식당'],
]
const short = (area) => area.replace(/동$/, '') // "성수동" → "성수"

export default function Home() {
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)
  const [areaName, setAreaName] = useState(null)

  useEffect(() => {
    setError(false)
    apiFetch(`/api/home/${category ? `?category=${category}` : ''}`)
      .then(setData)
      .catch(() => setError(true))
  }, [category])

  const area = data?.areas.find((a) => a.name === areaName) ?? data?.areas[0]
  // 큰 사진 자리: 이번 주 가장 많이 평가된 곳, 없으면 고른 동네의 첫 번째 장소
  const hero = data?.featured ?? area?.places[0]
  const word = category === 'FD6' ? '맛집' : '카페'

  return (
    <div className="home">
      <section className="hero">
        <div>
          <h1>밥 먹고,<br />카페 가고,<br />별점 남기고.</h1>
          <p>
            다녀온 카페와 식당을 기록하면
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
                <span>{data.featured ? `이번 주 평가 ${data.featured.week_count}개` : `요즘 ${short(area.name)}에서 많이 찾는 ${word}`}</span>
              </span>
            </Poster>
          </Link>
        )}
      </section>

      {error && <p className="error page" role="alert">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>}

      {data?.ranking.length > 0 && (
        <section className="sec" id="ranking">
          <div className="sec-head">
            <h2>카페피디아 별점 랭킹</h2>
            <Link to={`/ranking${category ? `?category=${category}` : ''}`} className="more">키워드·동네별 랭킹 보기</Link>
          </div>
          <div className="cards">{data.ranking.slice(0, 8).map((p, i) => <PlaceCard key={p.id} place={p} rank={i + 1} />)}</div>
        </section>
      )}

      {area && (
        <section className="sec">
          <div className="sec-head">
            <h2>요즘 {short(area.name)}에서 많이 가는 {word}</h2>
            <div className="seg" role="group" aria-label="분류">
              {KINDS.map(([code, label]) => (
                <button key={code} aria-pressed={category === code} onClick={() => setParams(code ? { category: code } : {})}>{label}</button>
              ))}
            </div>
          </div>
          <div className="cards">{area.places.slice(0, 8).map((p) => <PlaceCard key={p.id} place={p} />)}</div>
          <Link to={`/search?q=${area.name} ${word}`} className="more">{short(area.name)} {word} 더 보기</Link>
          <p className="muted small credit">동네별 목록은 카카오 장소 검색 결과 순서예요.</p>
        </section>
      )}

      {data?.recent.length > 0 && (
        <section className="sec">
          <div className="sec-head"><h2>방금 별점이 남겨진 곳</h2></div>
          <div className="cards">{data.recent.slice(0, 4).map((p) => <PlaceCard key={p.id} place={p} />)}</div>
        </section>
      )}
    </div>
  )
}
