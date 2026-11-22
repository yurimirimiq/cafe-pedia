import { Link } from 'react-router-dom'
import { mediaUrl } from '../api'
import { area } from './PlaceCard'
import Shots from './Shots'

// 글 한 개: 닉네임 → 📍 가게 이름 → 줄바꿈 그대로인 글 → 세로 사진 → 키워드 (X 의 📍 맛집 글 형식)
// 장소 화면처럼 어디 글인지 이미 아는 곳에선 review.place 가 없어서 📍 줄이 빠진다
export default function Post({ review: c }) {
  return (
    <div className="rv">
      <Link to={`/users/${c.user_id}`} className="avatar" aria-hidden="true" tabIndex={-1}>{c.nickname[0]}</Link>
      <div>
        <Link to={`/users/${c.user_id}`}><strong>{c.nickname}</strong></Link>
        {c.verified && <span className="badge">영수증 인증</span>}
        {c.revisit && <span className="again">또 갈래요</span>}
        {c.verified && <div className="meta">{Number(c.visited_on.slice(5, 7))}월 {Number(c.visited_on.slice(8))}일 방문</div>}
        {c.place && <Link to={`/place/${c.place.id}`} className="pin">📍 {c.place.name} · {area(c.place.address)}</Link>}
        {c.comment && <p>{c.comment}</p>}
        {c.photos.length > 0 && (
          <Shots>
            {c.photos.map((u) => (
              <a key={u} href={mediaUrl(u)} target="_blank" rel="noreferrer"><img src={mediaUrl(u)} alt={`${c.nickname}님이 올린 사진`} loading="lazy" /></a>
            ))}
          </Shots>
        )}
        {c.tags.length > 0 && <div className="rv-tags">{c.tags.map((t) => <span key={t}>{t}</span>)}</div>}
      </div>
      <span className="mini">{c.rating}</span>
    </div>
  )
}
