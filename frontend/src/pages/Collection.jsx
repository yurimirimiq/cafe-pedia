import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, errorText } from '../api'
import { useAuth } from '../auth'
import PlaceCard from '../components/PlaceCard'

// 컬렉션 하나: 제목·소개·만든 사람·좋아요, 담긴 장소. 만든 사람은 고치기·지우기·장소 빼기
export default function Collection() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [c, setC] = useState(null)
  const [status, setStatus] = useState('loading')
  const [editing, setEditing] = useState(null) // { title, description }
  const [error, setError] = useState('') // 고치기 폼 에러
  const [actionError, setActionError] = useState('') // 좋아요·지우기·빼기 실패

  useEffect(() => {
    apiFetch(`/api/collections/${id}/`)
      .then((data) => { setC(data); setStatus('done') })
      .catch((err) => setStatus(err.status === 404 ? 'notfound' : 'error'))
  }, [id, user])

  if (status === 'loading') return <p className="page muted">불러오는 중…</p>
  if (status === 'notfound') return <p className="page muted">이 컬렉션을 찾을 수 없어요. 지워졌을 수도 있어요.</p>
  if (status === 'error') return <p className="page error">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>

  const isOwner = user?.id === c.owner.id

  async function toggleLike() {
    if (!user) return navigate('/login')
    await act(async () => {
      const res = await apiFetch(`/api/collections/${id}/like/`, { method: c.liked ? 'DELETE' : 'POST' })
      setC((prev) => ({ ...prev, ...res }))
    }, '좋아요를 저장하지 못했어요.')
  }

  // 버튼 동작 하나를 실행하고, 실패하면 이유를 보여준다
  async function act(run, fallback) {
    setActionError('')
    try { await run() } catch (err) { setActionError(errorText(err, fallback)) }
  }

  async function save(e) {
    e.preventDefault()
    try {
      setC(await apiFetch(`/api/collections/${id}/`, { method: 'PATCH', body: editing }))
      setEditing(null)
      setError('')
    } catch (err) {
      setError(errorText(err, '저장하지 못했어요.'))
    }
  }

  async function remove() {
    if (!window.confirm(`"${c.title}" 컬렉션을 지울까요? 담긴 장소 목록도 함께 사라져요.`)) return
    await act(async () => {
      await apiFetch(`/api/collections/${id}/`, { method: 'DELETE' })
      navigate(`/collections?user=${user.id}`)
    }, '컬렉션을 지우지 못했어요.')
  }

  async function removePlace(placeId) {
    await act(async () => {
      const res = await apiFetch(`/api/collections/${id}/places/${placeId}/`, { method: 'DELETE' })
      setC((prev) => ({ ...prev, place_count: res.place_count, places: prev.places.filter((p) => p.id !== placeId) }))
    }, '장소를 빼지 못했어요.')
  }

  return (
    <section className="page collection">
      {editing ? (
        <form className="coll-form" onSubmit={save}>
          <label className="field">제목<input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} maxLength={40} autoFocus required /></label>
          <label className="field">소개<input value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} maxLength={200} /></label>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="form-foot">
            <button type="button" className="link" onClick={() => setEditing(null)}>취소</button>
            <button className="btn dark small" disabled={!editing.title.trim()}>저장</button>
          </div>
        </form>
      ) : (
        <header className="coll-detail-head">
          <h1>{c.title}</h1>
          {c.description && <p className="coll-desc">{c.description}</p>}
          <div className="coll-meta">
            <Link to={isOwner ? '/me' : `/users/${c.owner.id}`} className="coll-by">
              <span className="avatar">{c.owner.nickname[0]}</span>{c.owner.nickname}
            </Link>
            <span className="muted">{c.place_count}곳</span>
            <button className="btn small" onClick={toggleLike} aria-pressed={c.liked}>{c.liked ? '좋아요 ✓' : '좋아요'} {c.like_count}</button>
            {isOwner && (
              <>
                <button className="link small" onClick={() => setEditing({ title: c.title, description: c.description })}>고치기</button>
                <button className="link small" onClick={remove}>지우기</button>
              </>
            )}
          </div>
        </header>
      )}

      {actionError && <p className="error" role="alert">{actionError}</p>}
      {c.places.length === 0 ? (
        <p className="muted empty">
          {isOwner ? '아직 담긴 곳이 없어요. 장소 상세에서 "담기"를 눌러 채워 보세요. ' : '아직 담긴 곳이 없어요.'}
          {isOwner && <Link to="/search" className="rating">검색하러 가기</Link>}
        </p>
      ) : (
        <div className="cards">
          {c.places.map((p) => (
            <div key={p.id} className="coll-place">
              <PlaceCard place={p} />
              {isOwner && <button className="link small" onClick={() => removePlace(p.id)}>컬렉션에서 빼기</button>}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
