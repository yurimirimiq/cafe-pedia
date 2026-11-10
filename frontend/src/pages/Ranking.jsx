import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import PlaceCard from '../components/PlaceCard'

const CATEGORIES = [
  ['', '전체'],
  ['CE7', '카페'],
  ['FD6', '식당'],
]

// 랭킹: 분류·키워드·동네로 거른 베이지안 평균 순위. 조건은 주소(?category=&tag=&area=)에 담는다
export default function Ranking() {
  const [params, setParams] = useSearchParams()
  const category = params.get('category') ?? ''
  const tag = params.get('tag') ?? ''
  const area = params.get('area') ?? ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    setError(false)
    const q = new URLSearchParams({ ...(category && { category }), ...(tag && { tag }), ...(area && { area }) })
    apiFetch(`/api/rankings/?${q}`).then(setData).catch(() => setError(true))
  }, [category, tag, area])

  // 같은 칩을 다시 누르면 해제. 분류를 바꾸면 그 분류에 없는 키워드는 지운다
  function choose(key, value) {
    const next = Object.fromEntries(params)
    if (value && next[key] !== value) next[key] = value
    else delete next[key]
    if (key === 'category') delete next.tag
    setParams(next)
  }

  return (
    <section className="page ranking">
      <h1>카페피디아 별점 랭킹</h1>
      <p className="muted">평가가 적은 곳은 전체 평균 쪽으로 당겨서 순위를 매겨요. 별점 하나만으로는 1등이 되지 않아요.</p>

      <div className="seg" role="group" aria-label="분류">
        {CATEGORIES.map(([code, label]) => (
          <button key={code} aria-pressed={category === code} onClick={() => choose('category', code)}>{label}</button>
        ))}
      </div>
      {data && (
        <>
          <div className="filter-row" role="group" aria-label="키워드">
            <span>키워드</span>
            <div>
              {data.tags.map((t) => (
                <button key={t} className={`chip${tag === t ? ' on' : ''}`} aria-pressed={tag === t} onClick={() => choose('tag', t)}>{t}</button>
              ))}
            </div>
          </div>
          {data.areas.length > 0 && (
            <div className="filter-row" role="group" aria-label="동네">
              <span>동네</span>
              <div>
                {data.areas.map((a) => (
                  <button key={a} className={`chip${area === a ? ' on' : ''}`} aria-pressed={area === a} onClick={() => choose('area', a)}>{a}</button>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {error && <p className="error" role="alert">랭킹을 불러오지 못했어요. 잠시 후 다시 시도하세요.</p>}
      {data?.places.length === 0 && <p className="muted empty">이 조건에 맞는 평가된 곳이 아직 없어요. 키워드나 동네를 바꿔 보세요.</p>}
      {data?.places.length > 0 && (
        <div className="cards">{data.places.map((p, i) => <PlaceCard key={p.id} place={p} rank={i + 1} />)}</div>
      )}
    </section>
  )
}
