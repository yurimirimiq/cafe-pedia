import { Children, useRef, useState } from 'react'

// 사진 넘겨 보기: 한 장씩 보이고 좌우로 밀거나 화살표로 넘긴다 (인스타그램처럼)
// 넘기는 동작은 CSS scroll-snap 이 하고, 여기선 지금 몇 번째인지만 센다
export default function Shots({ children }) {
  const track = useRef(null)
  const [at, setAt] = useState(0)
  const n = Children.count(children)
  const i = Math.min(at, n - 1) // 보던 사진을 지워 장수가 줄어든 직후
  const go = (d) => track.current.scrollBy({ left: d * track.current.clientWidth })
  return (
    <div className="shots">
      <div className="track" ref={track} onScroll={(e) => setAt(Math.round(e.target.scrollLeft / e.target.clientWidth))}>
        {children}
      </div>
      {n > 1 && (
        <>
          <span className="count" aria-live="polite">{i + 1}/{n}</span>
          {i > 0 && <button type="button" className="prev" onClick={() => go(-1)} aria-label="이전 사진">‹</button>}
          {i < n - 1 && <button type="button" className="next" onClick={() => go(1)} aria-label="다음 사진">›</button>}
        </>
      )}
    </div>
  )
}
