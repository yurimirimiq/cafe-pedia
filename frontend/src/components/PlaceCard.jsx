import { Link } from 'react-router-dom'
import Poster from './Poster'

// 장소 키워드: 사용자가 가장 많이 고른 키워드, 아직 없으면 카카오 세부 분류(예: 디저트카페)
export const keywords = (place, n = 3) =>
  place.top_tags?.length ? place.top_tags.slice(0, n) : [place.category_detail.split(' > ').at(-1)]

// "서울 마포구 망원로 1" → "마포구"
export const area = (address) => address.split(' ')[1] ?? ''

// 사진 카드: 사진 위에 큰 별점 숫자, 아래에 이름과 키워드. rank 를 주면 왼쪽 위에 순위
// rating 을 주면 평균 대신 그 별점을 보여주고, 아래 글자는 label (기본: 내 별점)
// predicted 를 주면 속이 빈 숫자(내 예상 별점)와 오른쪽 아래 실제 평균. by 를 주면 이름 위에 누가 준 별점인지
export default function PlaceCard({ place, rank, rating, label = '내 별점', predicted, by }) {
  const score = predicted ?? rating ?? place.avg_rating
  return (
    <Link to={`/place/${place.id}`} className="card">
      <Poster place={place} className="card-photo">
        {rank && <span className="rank">{rank}</span>}
        {score ? <span className={predicted ? 'guess' : 'score'}>{score}</span> : <span className="no-score">아직 평가 없음</span>}
        {predicted && place.avg_rating && <span className="card-avg">평균 {place.avg_rating}<br />{place.review_count}명</span>}
      </Poster>
      {by && <span className="by"><span className="avatar">{by[0]}</span>{by}님의 별점</span>}
      <h3>{place.name}</h3>
      {!by && <p>{rating ? label : keywords(place, 2).join(', ')}</p>}
    </Link>
  )
}
