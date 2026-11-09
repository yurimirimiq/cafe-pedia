import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, mediaUrl } from '../api'
import { useAuth } from '../auth'
import PlaceMap from '../components/PlaceMap'
import { area, keywords } from '../components/PlaceCard'
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
  const [files, setFiles] = useState([]) // 새로 고른 사진 (아직 안 올림)

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
    setFiles([])
    setEditingComment(true)
  }

  const photoCount = (place?.my_review?.photos.length ?? 0) + files.length

  function pickFiles(e) {
    const picked = [...e.target.files]
    e.target.value = '' // 같은 파일을 다시 고를 수 있게
    if (photoCount + picked.length > 3) return setError('사진은 3장까지 올릴 수 있어요.')
    setError('')
    setFiles([...files, ...picked])
  }

  async function deletePhoto(photoId) {
    const res = await apiFetch(`/api/places/${id}/review/photos/${photoId}/`, { method: 'DELETE' })
    setPlace((p) => ({ ...p, ...res }))
  }

  // 한 줄 평 저장 → 새 사진이 있으면 이어서 올린다
  async function submitComment(e) {
    e.preventDefault()
    if (!(await saveReview({ comment: comment.trim() }))) return
    if (files.length) {
      const form = new FormData()
      files.forEach((f) => form.append('photos', f))
      setBusy(true)
      try {
        await apiFetch(`/api/places/${id}/review/photos/`, { method: 'POST', body: form })
      } catch (err) {
        setBusy(false)
        return setError(err.data?.detail ?? '사진을 올리지 못했어요.')
      }
      setBusy(false)
    }
    setFiles([])
    setEditingComment(false)
    load()
  }

  if (status === 'loading') return <p className="page muted">불러오는 중…</p>
  if (status === 'notfound') return <p className="page muted">이 장소를 찾을 수 없어요. 검색에서 다시 찾아보세요.</p>
  if (status === 'error') return <p className="page error">불러오지 못했어요. 잠시 후 다시 시도하세요.</p>

  const mine = place.my_review
  const tagCounts = place.tag_counts.length ? place.tag_counts : keywords(place).map((tag) => ({ tag }))
  return (
    <article className="place">
      <Poster place={place} className="place-hero">
        <div className="who">
          <h1>{place.name}</h1>
          <p>{area(place.address)}, {place.category_detail.split(' > ').at(-1)}</p>
        </div>
        {place.avg_rating && <span className="score">{place.avg_rating}</span>}
      </Poster>

      <div className="place-body">
        <div>
          <div className="rate">
            <div>
              <StarRating value={mine ? Number(mine.rating) : null} onChange={(v) => saveReview({ rating: v })} disabled={busy} />
              <p className="muted small">
                {place.review_count ? `${place.review_count}명이 평가했어요` : '첫 별점을 남겨 보세요'}
                {place.comments.length > 0 && <> · <a href="#comments">한 줄 평 {place.comments.length}개</a></>}
              </p>
            </div>
            <div className="rate-btns">
              <button className="btn" onClick={toggleWish} aria-pressed={place.wished}>{place.wished ? '가고 싶어요 ✓' : '가고 싶어요'}</button>
              <button className="btn dark" onClick={openComment}>{mine?.comment || mine?.photos.length ? '한 줄 평 고치기' : '한 줄 평 쓰기'}</button>
            </div>
          </div>
          {error && <p className="error" role="alert">{error}</p>}

          <ul className="tag-counts" aria-label="키워드">
            {tagCounts.map(({ tag, count }) => <li key={tag}>{tag}{count && <em>{count}</em>}</li>)}
          </ul>

          {mine && (
            <div className="mine">
              <label className="pill-date">
                <span>방문일</span>
                <input type="date" value={mine.visited_on} max={today()} onChange={(e) => e.target.value && saveReview({ visited_on: e.target.value })} />
              </label>
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
              <button className="link small" onClick={removeReview}>평가 지우기</button>
            </div>
          )}

          {editingComment && (
            <form className="comment-form" onSubmit={submitComment}>
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} maxLength={200} rows={3} placeholder="라떼가 진하고 창가 자리가 좋아요" autoFocus />
              <div className="photo-picker">
                {mine.photos.map((ph) => (
                  <span key={ph.id} className="thumb">
                    <img src={mediaUrl(ph.url)} alt="내가 올린 사진" />
                    <button type="button" onClick={() => deletePhoto(ph.id)} aria-label="사진 지우기">×</button>
                  </span>
                ))}
                {files.map((f, i) => (
                  <span key={i} className="thumb">
                    <img src={URL.createObjectURL(f)} alt="올릴 사진 미리보기" />
                    <button type="button" onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label="고른 사진 빼기">×</button>
                  </span>
                ))}
                {photoCount < 3 && (
                  <label className="thumb add">
                    <input type="file" accept="image/*" multiple onChange={pickFiles} className="sr-only" />
                    + 사진
                  </label>
                )}
              </div>
              <div className="form-foot">
                <span className="muted small">{comment.length}/200</span>
                <button type="button" className="link" onClick={() => setEditingComment(false)}>취소</button>
                <button className="btn dark small" disabled={busy}>저장</button>
              </div>
            </form>
          )}

          <section className="reviews" id="comments">
            <h2>한 줄 평 {place.comments.length}</h2>
            {place.comments.length === 0 && <p className="muted">아직 한 줄 평이 없어요. 다녀왔다면 첫 한 줄 평을 남겨 보세요.</p>}
            {place.comments.map((c) => (
              <div key={c.id} className="rv">
                <span className="avatar">{c.nickname[0]}</span>
                <div>
                  <strong>{c.nickname}</strong>
                  {c.comment && <p>{c.comment}</p>}
                  {c.photos.length > 0 && (
                    <div className="shots">
                      {c.photos.map((u) => (
                        <a key={u} href={mediaUrl(u)} target="_blank" rel="noreferrer"><img src={mediaUrl(u)} alt={`${c.nickname}님이 올린 사진`} loading="lazy" /></a>
                      ))}
                    </div>
                  )}
                  {c.tags.length > 0 && <p className="muted small">{c.tags.join(', ')}</p>}
                </div>
                <span className="mini">{c.rating}</span>
              </div>
            ))}
          </section>
        </div>

        <aside className="side">
          <PlaceMap place={place} />
          <dl>
            <dt>주소</dt><dd>{place.address}</dd>
            {mine && <><dt>방문</dt><dd>{mine.visited_on.replaceAll('-', '. ')}에 다녀왔어요</dd></>}
          </dl>
          {place.thumbnail_source && <a className="photo-credit" href={place.thumbnail_source} target="_blank" rel="noreferrer">대표 사진 출처 보기</a>}
          <NearbyPicks place={place} />
        </aside>
      </div>
    </article>
  )
}

// 카페 상세에선 근처 식당, 식당 상세에선 근처 카페 (500m 안, 가까운 순 3곳)
function NearbyPicks({ place }) {
  const [picks, setPicks] = useState(null)
  const other = place.category === 'CE7' ? 'FD6' : 'CE7'

  useEffect(() => {
    const q = new URLSearchParams({ lat: Number(place.latitude).toFixed(3), lng: Number(place.longitude).toFixed(3), radius: 500, category: other })
    apiFetch(`/api/places/nearby/?${q}`)
      .then((list) => setPicks(list.filter((p) => p.id !== place.id).slice(0, 3)))
      .catch(() => setPicks([]))
  }, [place.id]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!picks?.length) return null
  return (
    <div className="near">
      <h3>{other === 'FD6' ? '여기서 밥 먹고 가기' : '밥 먹고 여기서 커피 한 잔'}</h3>
      {picks.map((p) => (
        <Link key={p.id} to={`/place/${p.id}`}>
          <Poster place={p} className="near-photo" />
          <span>{p.name}<small>도보 {Math.max(1, Math.round(p.distance / 70))}분</small></span>
          {p.avg_rating && <b>{p.avg_rating}</b>}
        </Link>
      ))}
    </div>
  )
}
