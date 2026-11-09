import { useState } from 'react'

// 별 하나 = 왼쪽 반(0.5) + 오른쪽 반(1.0) 버튼 두 개. 별 5개로 0.5~5.0 을 고른다
export default function StarRating({ value, onChange, disabled }) {
  const [hover, setHover] = useState(null)
  const shown = hover ?? value ?? 0

  return (
    <div className="stars-input">
      <div className="stars" role="radiogroup" aria-label="별점" onMouseLeave={() => setHover(null)}>
        {[1, 2, 3, 4, 5].map((star) => {
          // 이 별이 얼마나 채워졌는지: 0, 50, 100 (%)
          const fill = shown >= star ? 100 : shown >= star - 0.5 ? 50 : 0
          return (
            <span key={star} className="star">
              <span className="star-bg">★</span>
              <span className="star-fill" style={{ width: `${fill}%` }}>★</span>
              {[star - 0.5, star].map((v) => (
                <button
                  key={v}
                  type="button"
                  className={v % 1 ? 'half left' : 'half right'}
                  role="radio"
                  aria-checked={value === v}
                  aria-label={`${v.toFixed(1)}점`}
                  disabled={disabled}
                  onMouseEnter={() => setHover(v)}
                  onFocus={() => setHover(v)}
                  onBlur={() => setHover(null)}
                  onClick={() => onChange(v)}
                />
              ))}
            </span>
          )
        })}
      </div>
    </div>
  )
}
