import { Link } from 'react-router-dom'
import Poster from './Poster'

// 장소 키워드: 사용자가 가장 많이 고른 키워드, 아직 없으면 카카오 세부 분류(예: 디저트카페)
export const keywords = (place, n = 3) =>
  place.top_tags?.length ? place.top_tags.slice(0, n) : [place.category_detail.split(' > ').at(-1)]

// "서울 마포구 망원로 1" → "마포구"
export const area = (address) => address.split(' ')[1] ?? ''

// 포스터 + 이름 + 동네 + 별점. rank 를 주면 왼쪽 위에 순위를 표시한다
export default function PlaceCard({ place, rank, rating }) {
  return (
    <Link to={`/place/${place.id}`} className="card">
      <div className="card-poster">
        <Poster place={place} />
        {rank && <span className="rank">{rank}</span>}
        <span className="tag">{place.category_label}</span>
      </div>
      <div className="card-name">{place.name}</div>
      <div className="muted small ellipsis">{area(place.address)}, {keywords(place, 2).join(' · ')}</div>
      <div className="rating small">
        {rating ? `내 별점 ★${rating}` : place.avg_rating ? `평균 ★${place.avg_rating}` : '평가 없음'}
      </div>
    </Link>
  )
}
