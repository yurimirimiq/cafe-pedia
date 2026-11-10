import { Link } from 'react-router-dom'
import Poster from './Poster'

// 컬렉션 카드: 담긴 장소 사진 5장을 이어 붙인 띠 + 만든 사람 + 장소 수, 아래에 제목·소개·좋아요
export default function CollectionCard({ collection: c }) {
  // 장소가 5곳보다 적으면 남는 칸은 커피색 타일
  const covers = Array.from({ length: 5 }, (_, i) => c.covers[i] ?? { id: c.id + i })
  return (
    <Link to={`/collections/${c.id}`} className="coll-card">
      <div className="coll-covers">
        {covers.map((p, i) => <Poster key={i} place={p} className="coll-cover" />)}
        <span className="coll-owner"><span className="avatar">{c.owner.nickname[0]}</span>{c.owner.nickname}</span>
        <span className="coll-count">{c.place_count}곳</span>
      </div>
      <div className="coll-body">
        <h3>{c.title}</h3>
        {c.description && <p>{c.description}</p>}
        <span className="coll-likes">좋아요 {c.like_count}</span>
      </div>
    </Link>
  )
}
