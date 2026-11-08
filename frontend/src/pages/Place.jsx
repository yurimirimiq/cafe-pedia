import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import PlaceMap from '../components/PlaceMap'
import { keywords } from '../components/PlaceCard'
import Poster from '../components/Poster'
import StarRating from '../components/StarRating'

const today = () => new Date().toLocaleDateString('sv') // YYYY-MM-DD (내 컴퓨터 시간 기준)

// 서버 에러 {필드: [메시지]} 를 한 줄로
const errorText = (err) =>
  err.data && typeof err.data === 'object' ? Object.values(err.data).flat().join(' ') : '저장하지 못했어요. 잠시 후 다시 시도하세요.'

export default function Place() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [place, setPlace] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editingComment, setEditingComment] = useState(false)
  const [comment, setComment] = useState('')

  const load = () =>
    apiFetch(`/api/places/${id}/`)
      .then((p) => { setPlace(p); setStatus('done') })
      .catch((err) => setStatus(err.status === 404 ? 'notfound' : 'error'))

  // 로그인 상태가 바뀌면 내 별점·가고 싶어요를 다시 불러온다
  useEffect(() => { load() }, [id, user]) // eslint-disable-line react-hooks/exhaustive-deps

  // 별점·방문일·한 줄 평 저장 (보낸 값만 바뀐다)
  async function saveReview(changes) {
    if (!user) return navigate('/login')
    setBusy(true)
    setError('')
    try {
      const res = await apiFetch(`/api/places/${id}/review/`, { method: 'PUT', body: changes })
      setPlace((p) => ({ ...p, ...res }))
      return true
    } catch (err) {
      setError(errorText(err))
      return false
    } finally {
      setBusy(false)
    }
  }

  // 키워드 고르기·빼기 (최대 3개). 저장 후 다시 불러와 장소 키워드도 갱신한다
  async function toggleTag(tag) {
    const current = place.my_review.tags
    const next = current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag]
    if (next.length > 3) return setError('키워드는 3개까지 고를 수 있어요.')
    if (await saveReview({ tags: next })) load()
  }

  async function removeReview() {
    const res = await apiFetch(`/api/places/${id}/review/`, { method: 'DELETE' })
    setPlace((p) => ({ ...p, ...res }))
    load() // 한 줄 평 목록도 갱신
  }

  async function toggleWish() {
    if (!user) return navigate('/login')
    const res = await apiFetch(`/api/places/${id}/wish/`, { method: place.wished ? 'DELETE' : 'POST' })
    setPlace((p) => ({ ...p, ...res }))
  }

  function openComment() {
    if (!user) return navigate('/login')
    if (!place.my_review) return setError('별점을 먼저 남겨 주세요.')
    setComment(place.my_review.comment)
    setEditingComment(true)
  }

  async function submitComment(e) {
    e.preventDefault()
    if (await saveReview({ comment: comment.trim() })) {
      setEditingComment(false)
      load()
    }
  }

  if (status === 'loading') return <p className="page muted">불러오는 중…</p>
  if (status === 'notfound') return <p className="page muted">이 장소를 찾을 수 없어요. 검색에서 다시 찾아보세요.</p>
  if (status === 'error') return <p className="page error">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>

  const mine = place.my_review
  return (
    <article className="page place">
      <div className="place-head">
        <div>
          <Poster place={place} />
          {place.thumbnail_source && (
            <a className="photo-credit" href={place.thumbnail_source} target="_blank" rel="noreferrer">사진 출처 보기</a>
          )}
        </div>
        <div className="place-main">
          <h1>{place.name}</h1>
          <p className="muted">{place.category_detail.split(' > ').slice(1).join(', ') || place.category_label} / {place.address}</p>

          <ul className="keywords" aria-label="키워드">
            {keywords(place).map((k) => <li key={k}>{k}</li>)}
          </ul>

          <div className="avg">
            {place.avg_rating && <span className="avg-num">{place.avg_rating}</span>}
            <span className="muted">{place.review_count ? `${place.review_count}명이 평가했어요` : '아직 평가가 없어요. 첫 별점을 남겨 보세요'}</span>
          </div>

          <div className="actions">
            <StarRating value={mine ? Number(mine.rating) : null} onChange={(v) => saveReview({ rating: v })} disabled={busy} />
            {mine && (
              <label className="btn visit">
                <span>방문일</span>
                <input type="date" value={mine.visited_on} max={today()} onChange={(e) => e.target.value && saveReview({ visited_on: e.target.value })} />
              </label>
            )}
            <button className="btn" onClick={toggleWish} aria-pressed={place.wished}>
              {place.wished ? '✓ 가고 싶어요' : '+ 가고 싶어요'}
            </button>
            <button className="btn" onClick={openComment}>{mine?.comment ? '한 줄 평 고치기' : '한 줄 평'}</button>
          </div>
          {mine && (
            <div className="tag-picker">
              <span className="muted small">이곳을 키워드로 표현하면? (최대 3개)</span>
              <div className="chips">
                {place.tag_options.map((t) => (
                  <button key={t} className={`chip${mine.tags.includes(t) ? ' on' : ''}`} aria-pressed={mine.tags.includes(t)} onClick={() => toggleTag(t)} disabled={busy}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}
          {mine && <button className="link small" onClick={removeReview}>평가 지우기</button>}
          {error && <p className="error" role="alert">{error}</p>}

          {editingComment && (
            <form className="comment-form" onSubmit={submitComment}>
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={200} rows={2} placeholder="라떼가 진하고 창가 자리가 좋아요" autoFocus />
              <div>
                <span className="muted small">{comment.length}/200</span>
                <button type="button" className="link" onClick={() => setEditingComment(false)}>취소</button>
                <button className="btn primary small" disabled={busy}>저장</button>
              </div>
            </form>
          )}
        </div>
        <PlaceMap place={place} />
      </div>

      <section className="comments">
        <h2>한 줄 평 <span className="muted">{place.comments.length}</span></h2>
        {place.comments.length === 0 ? (
          <p className="muted">아직 한 줄 평이 없어요.</p>
        ) : (
          <ul>
            {place.comments.map((c) => (
              <li key={c.id} className="comment">
                <div><strong>{c.nickname}</strong><span className="rating">★ {c.rating}</span></div>
                <p>{c.comment}</p>
                {c.tags.length > 0 && <p className="muted small">{c.tags.join(' · ')}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  )
}
