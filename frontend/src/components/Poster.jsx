import { useState } from 'react'
import { mediaUrl } from '../api'

// 장소 사진: 원본 → (막히면) 미리보기 → (그것도 안 되면) 필름 카메라로 흐리게 찍은 듯한 커피색 그라데이션
export default function Poster({ place, className = '', children }) {
  const [broken, setBroken] = useState([]) // 불러오지 못한 사진 주소들
  const tone = `tone-${place.id % 6}` // 같은 장소는 항상 같은 색
  const src = [place.thumbnail_url, place.thumbnail_fallback].find((u) => u && !broken.includes(u))

  return (
    <div className={`poster ${src ? 'photo' : tone} ${className}`}>
      {src && (
        <img key={src} src={mediaUrl(src)} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken((b) => [...b, src])} />
      )}
      {children}
    </div>
  )
}
