import { useState } from 'react'

// 사진이 없을 때 쓰는 커피색 타일 (README 디자인 방향)
const TONES = [
  ['#3B2A21', '#EFE6DC'], // 에스프레소
  ['#C8A27C', '#3B2A21'], // 크레마
  ['#EFE6DC', '#7A4A2B'], // 라떼
  ['#7A4A2B', '#EFE6DC'], // 브라운
]

// 장소 포스터: 썸네일 사진이 있으면 사진, 없거나 불러오기에 실패하면 커피색 타일 + 이름 첫 글자
export default function Poster({ place, size }) {
  const [broken, setBroken] = useState(false)
  // 같은 장소는 항상 같은 색이 나오도록 id 로 고른다
  const [bg, fg] = TONES[place.id % TONES.length]
  const first = place.name.replace(/^(카페|cafe)\s*/i, '')[0] ?? place.name[0]

  if (place.thumbnail_url && !broken) {
    return (
      <div className="poster photo" style={{ background: bg, width: size }}>
        <img src={place.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      </div>
    )
  }
  return (
    <div className="poster" style={{ background: bg, color: fg, width: size }} aria-hidden="true">
      {first}
    </div>
  )
}
