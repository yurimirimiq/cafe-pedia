import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { keywords } from '../components/PlaceCard'
import Poster from '../components/Poster'

const CATEGORIES = [['', '전체'], ['CE7', '카페'], ['FD6', '식당']]
const RADII = [[500, '500m'], [1000, '1km'], [3000, '3km']]
const SORTS = [['distance', '가까운 순'], ['rating', '별점 높은 순']]

const meters = (m) => (m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`)

// 위치 권한 거절 등 브라우저가 알려주는 이유를 사람이 읽을 문장으로
const LOCATION_ERRORS = {
  1: '위치 권한이 꺼져 있어요. 브라우저 주소창의 위치 아이콘에서 허용한 뒤 다시 눌러 주세요.',
  2: '현재 위치를 알 수 없어요. 잠시 후 다시 시도해 주세요.',
  3: '위치를 찾는 데 시간이 너무 오래 걸렸어요. 다시 시도해 주세요.',
}

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
    if (!navigator.geolocation) {
      setStatus('error')
      return setMessage('이 브라우저는 위치 찾기를 지원하지 않아요.')
    }
    setStatus('locating')
    navigator.geolocation.getCurrentPosition(
      // 소수점 3자리(약 100m)로 줄여서 보낸다: 주변 검색엔 충분하고 정확한 위치는 남기지 않는다
      ({ coords: c }) => setCoords({ lat: c.latitude.toFixed(3), lng: c.longitude.toFixed(3) }),
      (err) => { setStatus('error'); setMessage(LOCATION_ERRORS[err.code] ?? LOCATION_ERRORS[2]) },
      { timeout: 10000, maximumAge: 60000 },
    )
  }

  useEffect(() => {
    if (!coords) return
    let ignore = false
    setStatus('loading')
    apiFetch(`/api/places/nearby/?${new URLSearchParams({ ...coords, radius, ...(category && { category }) })}`)
      .then((data) => { if (!ignore) { setPlaces(data); setStatus('done') } })
      .catch((err) => { if (!ignore) { setStatus('error'); setMessage(err.data?.detail ?? '주변을 찾지 못했어요. 잠시 후 다시 시도하세요.') } })
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
          <p className="muted">지금 있는 곳 근처의 카페·식당과 별점을 보여드려요. 위치는 검색에만 쓰고 저장하지 않아요.</p>
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
      {status === 'done' && sorted.length === 0 && <p className="muted">{meters(radius)} 안에 카페·식당이 없어요. 거리를 넓혀 보세요.</p>}

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
