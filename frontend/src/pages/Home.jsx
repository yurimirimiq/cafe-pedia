import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import PlaceCard, { area } from '../components/PlaceCard'

const TABS = [
  ['', '홈'],
  ['CE7', '카페'],
  ['FD6', '식당'],
]

export default function Home() {
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    setError(false)
    apiFetch(`/api/home/${category ? `?category=${category}` : ''}`)
      .then(setData)
      .catch(() => setError(true))
  }, [category])

  return (
    <section className="page home">
      <div className="tabs" role="tablist">
        {TABS.map(([code, label]) => (
          <button key={code} role="tab" aria-selected={category === code} onClick={() => setParams(code ? { category: code } : {})}>
            {label}
          </button>
        ))}
      </div>

      {error && <p className="error" role="alert">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>}
      {data && (
        <>
          <div className="home-top">
            {data.featured ? (
              <Link to={`/place/${data.featured.id}`} className="featured">
                <span>이번 주 가장 많이 평가된 곳</span>
                <strong>{area(data.featured.address)} {data.featured.name}</strong>
                <span>평균 ★{data.featured.avg_rating}, 이번 주 평가 {data.featured.week_count}개</span>
              </Link>
            ) : (
              <Link to="/search" className="featured">
                <span>아직 이번 주 평가가 없어요</span>
                <strong>첫 별점을 남겨 보세요</strong>
                <span>다녀온 카페와 식당을 검색해서 평가할 수 있어요</span>
              </Link>
            )}
            <div className="shortcuts">
              <Link to="/search">평가하기</Link>
              <Link to="/me">취향 분석</Link>
              <a href="#ranking">랭킹</a>
            </div>
            <p className="total">지금까지 <b>★ {data.total_reviews.toLocaleString()}개</b>의 평가가 쌓였어요</p>
          </div>

          <h2 id="ranking">카페피디아 인기 랭킹</h2>
          {data.ranking.length ? (
            <div className="row">{data.ranking.map((p, i) => <PlaceCard key={p.id} place={p} rank={i + 1} />)}</div>
          ) : (
            <p className="muted">아직 평가된 곳이 없어요. <Link to="/search" className="rating">검색해서 첫 별점 남기기</Link></p>
          )}

          {data.recent.length > 0 && (
            <>
              <h2>최근 평가된 곳</h2>
              <div className="row">{data.recent.map((p) => <PlaceCard key={p.id} place={p} />)}</div>
            </>
          )}
        </>
      )}
    </section>
  )
}
