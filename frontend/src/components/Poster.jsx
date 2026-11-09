import { useState } from 'react'
import { mediaUrl } from '../api'

// 장소 사진. 사진이 없거나 깨지면 필름 카메라로 흐리게 찍은 듯한 커피색 그라데이션으로 대신한다
export default function Poster({ place, className = '', children }) {
  const [broken, setBroken] = useState(false)
  const tone = `tone-${place.id % 6}` // 같은 장소는 항상 같은 색
  const photo = place.thumbnail_url && !broken

  return (
    <div className={`poster ${photo ? 'photo' : tone} ${className}`}>
      {photo && (
        <img src={mediaUrl(place.thumbnail_url)} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      )}
      {children}
    </div>
  )
}
