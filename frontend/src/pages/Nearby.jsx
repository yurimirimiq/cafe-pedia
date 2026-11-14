import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import { keywords } from '../components/PlaceCard'
import Poster from '../components/Poster'
import { getCoords, meters } from '../location'

const CATEGORIES = [['', '전체'], ['CE7', '카페'], ['FD6', '식당'], ['BAR', '술집']]
const RADII = [[500, '500m'], [1000, '1km'], [3000, '3km']]
const SORTS = [['distance', '가까운 순'], ['rating', '별점 높은 순']]

export default function Nearby() {
  const [coords, setCoords] = useState(null)
  const [status, setStatus] = useState('idle') // idle → locating → loading → done | error
  const [message, setMessage] = useState('')
  const [category, setCategory] = useState('')
  const [radius, setRadius] = useState(1000)
  const [sort, setSort] = useState('distance')
  const [places, setPlaces] = useState([])

  // 위치 권한 요청은 사용자가 버튼을 눌렀을 때만 한다 (페이지를 열자마자 묻지 않기)
  function locate() {
    setStatus('locating')
    getCoords().then(setCoords, (err) => { setStatus('error'); setMessage(err.message) })
  }

  useEffect(() => {
    if (!coords) return
    let ignore = false
    setStatus('loading')
    apiFetch(`/api/places/nearby/?${new URLSearchParams({ ...coords, radius, ...(category && { category }) })}`)
      .then((data) => { if (!ignore) { setPlaces(data); setStatus('done') } })
      .catch((err) => { if (!ignore) { setStatus('error'); setMessage(errorText(err, '주변을 찾지 못했어요. 잠시 후 다시 시도하세요.')) } })
    return () => { ignore = true }
  }, [coords, radius, category])

  const sorted = sort === 'rating'
    ? [...places].sort((a, b) => (Number(b.avg_rating) || 0) - (Number(a.avg_rating) || 0) || a.distance - b.distance)
    : places

  return (
    <section className="page search">
      <h1>내 주변</h1>
      {!coords && (
        <div className="locate">
          <p className="muted">지금 있는 곳 근처의 카페·식당·술집과 별점을 보여드려요. 위치는 검색에만 쓰고 저장하지 않아요.</p>
          <button className="btn primary" onClick={locate} disabled={status === 'locating'}>
            {status === 'locating' ? '위치 찾는 중…' : '내 위치로 찾기'}
          </button>
        </div>
      )}

      {coords && (
        <div className="filters">
          {[[CATEGORIES, category, setCategory, '분류'], [RADII, radius, setRadius, '거리'], [SORTS, sort, setSort, '정렬']].map(([options, value, set, label]) => (
            <div key={label} className="chips" role="group" aria-label={label}>
              {options.map(([v, text]) => (
                <button key={v} className={`chip${value === v ? ' on' : ''}`} aria-pressed={value === v} onClick={() => set(v)}>{text}</button>
              ))}
            </div>
          ))}
          <button className="link small" onClick={locate}>위치 다시 찾기</button>
        </div>
      )}

      {status === 'loading' && <p className="muted">주변을 찾는 중…</p>}
      {status === 'error' && <p className="error" role="alert">{message}</p>}
      {status === 'done' && sorted.length === 0 && <p className="muted">{meters(radius)} 안에 카페·식당·술집이 없어요. 거리를 넓혀 보세요.</p>}

      {sorted.length > 0 && status !== 'error' && (
        <ul className="results" aria-busy={status === 'loading'}>
          {sorted.map((p) => (
            <li key={p.id}>
              <Link to={`/place/${p.id}`} className="result">
                <Poster place={p} className="list-photo" />
                <div className="result-body">
                  <strong>{p.name}</strong>
                  <span className="muted">{meters(p.distance)} · {[p.category_label, ...keywords(p, 2)].filter((v, i, a) => a.indexOf(v) === i).join(' · ')}</span>
                  <span className="muted small">{p.address}</span>
                </div>
                {p.review_count ? <span className="rating">{p.avg_rating}</span> : <span className="muted small">평가 없음</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {coords && <p className="muted small credit">장소 정보 출처: 카카오</p>}
    </section>
  )
}
