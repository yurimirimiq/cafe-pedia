import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import Poster from '../components/Poster'

const FILTERS = [
  ['', '전체'],
  ['CE7', '카페'],
  ['FD6', '식당'],
  ['BAR', '술집'],
]

export default function Calendar() {
  const now = new Date()
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [category, setCategory] = useState('')
  const [visits, setVisits] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false // 달을 빨리 넘겼을 때 늦게 온 이전 달 결과를 무시
    setVisits(null)
    setError('')
    apiFetch(`/api/me/calendar/?${new URLSearchParams({ ...ym, ...(category && { category }) })}`)
      .then((v) => !ignore && setVisits(v))
      .catch((err) => !ignore && setError(errorText(err)))
    return () => { ignore = true }
  }, [ym, category])

  const move = (d) => setYm(({ year, month }) => {
    const m = month + d
    return m < 1 ? { year: year - 1, month: 12 } : m > 12 ? { year: year + 1, month: 1 } : { year, month: m }
  })

  // 달력 칸: 1일 앞의 빈칸(요일 맞추기) + 날짜 + 마지막 주 빈칸
  const firstDay = new Date(ym.year, ym.month - 1, 1).getDay()
  const days = new Date(ym.year, ym.month, 0).getDate()
  const cells = [...Array(firstDay).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)]
  while (cells.length % 7) cells.push(null)

  const byDay = {}
  for (const v of visits ?? []) (byDay[Number(v.date.slice(8))] ??= []).push(v)
  const isToday = (d) => d === now.getDate() && ym.month === now.getMonth() + 1 && ym.year === now.getFullYear()
  const count = (code) => visits.filter((v) => v.place.category === code).length

  return (
    <section className="page calendar">
      <div className="cal-head">
        <div className="cal-month">
          <button className="link" onClick={() => move(-1)} aria-label="이전 달">‹</button>
          <h1>{ym.year}년 {ym.month}월</h1>
          <button className="link" onClick={() => move(1)} aria-label="다음 달">›</button>
        </div>
        <div className="chips" role="group" aria-label="분류">
          {FILTERS.map(([code, label]) => (
            <button key={code} className={`chip${category === code ? ' on' : ''}`} aria-pressed={category === code} onClick={() => setCategory(code)}>{label}</button>
          ))}
        </div>
        {visits && <span className="muted small">이번 달 카페 {count('CE7')}곳, 식당 {count('FD6')}곳, 술집 {count('BAR')}곳</span>}
        <Link to="/search" className="btn primary small">+ 기록 추가</Link>
      </div>

      <div className="cal-grid">
        {'일월화수목금토'.split('').map((d) => <div key={d} className="cal-dow">{d}</div>)}
        {cells.map((d, i) => (
          <div key={i} className="cal-cell">
            {d && <span className={`cal-day${isToday(d) ? ' today' : ''}`}>{d}</span>}
            {byDay[d]?.slice(0, 2).map((v) => (
              <Link key={v.place.id} to={`/place/${v.place.id}`} title={`${v.place.name} ★${v.rating}`}>
                <Poster place={v.place} />
              </Link>
            ))}
            {byDay[d]?.length > 2 && <span className="muted small">+{byDay[d].length - 2}</span>}
          </div>
        ))}
      </div>
      {error && <p className="error" role="alert">기록을 불러오지 못했어요. {error}</p>}
      {visits?.length === 0 && <p className="muted">이 달에 남긴 기록이 없어요. 다녀온 곳을 검색해서 별점과 방문일을 남겨 보세요.</p>}
    </section>
  )
}
