import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import CollectionCard from '../components/CollectionCard'
import PlaceCard from '../components/PlaceCard'

// 다른 사용자의 프로필: 평가 수·팔로워·팔로잉, 팔로우 버튼, 최근 평가한 곳
export default function UserProfile() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [person, setPerson] = useState(null)
  const [status, setStatus] = useState('loading')
  const [busy, setBusy] = useState(false)
  const [colls, setColls] = useState([])

  useEffect(() => {
    setStatus('loading')
    apiFetch(`/api/users/${id}/`)
      .then((p) => { setPerson(p); setStatus('done') })
      .catch((err) => setStatus(err.status === 404 ? 'notfound' : 'error'))
    apiFetch(`/api/collections/?user=${id}`).then(setColls).catch(() => setColls([]))
  }, [id, user])

  async function toggleFollow() {
    if (!user) return navigate('/login')
    setBusy(true)
    try {
      const res = await apiFetch(`/api/users/${id}/follow/`, { method: person.is_following ? 'DELETE' : 'POST' })
      setPerson((p) => ({ ...p, is_following: res.is_following, counts: { ...p.counts, followers: res.followers } }))
    } finally {
      setBusy(false)
    }
  }

  if (user && String(user.id) === id) return <Navigate to="/me" replace />
  if (status === 'loading') return <p className="page muted">불러오는 중…</p>
  if (status === 'notfound') return <p className="page muted">이 사용자를 찾을 수 없어요.</p>
  if (status === 'error') return <p className="page error">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>

  const { counts } = person
  return (
    <section className="page me">
      <aside>
        <div className="profile-head">
          <div className="avatar big other">{person.nickname[0]}</div>
          <div>
            <h1>{person.nickname}</h1>
            {person.top_tag && <p className="follow-counts">자주 고르는 키워드: {person.top_tag}</p>}
          </div>
        </div>
        <div className="counts">
          <div><b>{counts.reviews}</b><span>평가</span></div>
          <div><b>{counts.followers}</b><span>팔로워</span></div>
          <div><b>{counts.following}</b><span>팔로잉</span></div>
        </div>
        <button className={`btn wide${person.is_following ? '' : ' dark'}`} onClick={toggleFollow} disabled={busy} aria-pressed={person.is_following}>
          {person.is_following ? '팔로잉 ✓' : '팔로우'}
        </button>
      </aside>

      <div>
        {colls.length > 0 && (
          <>
            <h2>{person.nickname}님의 컬렉션</h2>
            <div className="coll-grid profile-colls">{colls.map((c) => <CollectionCard key={c.id} collection={c} />)}</div>
          </>
        )}
        <h2>{person.nickname}님이 평가한 곳</h2>
        {person.reviews.length ? (
          <div className="grid">{person.reviews.map((p) => <PlaceCard key={p.id} place={p} rating={p.rating} label={`${person.nickname}님의 별점`} />)}</div>
        ) : (
          <p className="muted">아직 평가한 곳이 없어요.</p>
        )}
      </div>
    </section>
  )
}
