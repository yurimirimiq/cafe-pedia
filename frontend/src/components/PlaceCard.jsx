import { Link } from 'react-router-dom'
import Poster from './Poster'

// 장소 키워드: 사용자가 가장 많이 고른 키워드, 아직 없으면 카카오 세부 분류(예: 디저트카페)
export const keywords = (place, n = 3) =>
  place.top_tags?.length ? place.top_tags.slice(0, n) : [place.category_detail.split(' > ').at(-1)]

// "서울 마포구 망원로 1" → "마포구"
export const area = (address) => address.split(' ')[1] ?? ''

// 사진 카드: 사진 위에 큰 별점 숫자, 아래에 이름과 키워드. rank 를 주면 왼쪽 위에 순위
export default function PlaceCard({ place, rank, rating }) {
  const score = rating ?? place.avg_rating
  return (
    <Link to={`/place/${place.id}`} className="card">
      <Poster place={place} className="card-photo">
        {rank && <span className="rank">{rank}</span>}
        {score ? <span className="score">{score}</span> : <span className="no-score">아직 평가 없음</span>}
      </Poster>
      <h3>{place.name}</h3>
      <p>{rating ? '내 별점' : keywords(place, 2).join(', ')}</p>
    </Link>
  )
}
