import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import CollectionCard from '../components/CollectionCard'

const SORTS = [
  ['popular', '인기순'],
  ['recent', '최신순'],
]

// 컬렉션 둘러보기 (?user= 면 그 사람의 컬렉션) + 새 컬렉션 만들기
export default function Collections() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const owner = params.get('user') ?? ''
  const sort = params.get('sort') ?? 'popular'
  const [list, setList] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState(null) // null 이면 닫힘, { title, description }
  const mine = user && owner === String(user.id)

  useEffect(() => {
    setList(null)
    const q = new URLSearchParams({ ...(owner ? { user: owner } : { sort }) })
    apiFetch(`/api/collections/?${q}`).then(setList).catch(() => setList([]))
  }, [owner, sort, user])

  function openForm() {
    if (!user) return navigate('/login')
    setError('')
    setForm({ title: '', description: '' })
  }

  async function create(e) {
    e.preventDefault()
    try {
      const made = await apiFetch('/api/collections/', { method: 'POST', body: form })
      navigate(`/collections/${made.id}`)
    } catch (err) {
      setError(err.data?.detail || Object.values(err.data ?? {}).flat().join(' ') || '만들지 못했어요.')
    }
  }

  const heading = mine ? '내 컬렉션' : owner ? `${list?.[0]?.owner.nickname ?? ''}님의 컬렉션` : '컬렉션'

  return (
    <section className="page collections">
      <div className="coll-head">
        <div>
          <h1>{heading}</h1>
          {!owner && <p className="muted">카공하기 좋은 카페, 혼밥 맛집처럼 사람들이 직접 묶은 장소 목록이에요.</p>}
        </div>
        {(!owner || mine) && !form && <button className="btn dark" onClick={openForm}>새 컬렉션 만들기</button>}
      </div>

      {form && (
        <form className="coll-form" onSubmit={create}>
          <label className="field">
            제목
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} maxLength={40} placeholder="예: 카공하기 좋은 카페" autoFocus required />
          </label>
          <label className="field">
            소개 (선택)
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={200} placeholder="예: 콘센트 많고 오래 있어도 눈치 안 보이는 곳" />
          </label>
          <p className="muted small">컬렉션은 모두에게 공개돼요. 장소는 장소 상세의 "담기" 버튼으로 넣을 수 있어요.</p>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="form-foot">
            <button type="button" className="link" onClick={() => setForm(null)}>취소</button>
            <button className="btn dark small" disabled={!form.title.trim()}>만들기</button>
          </div>
        </form>
      )}

      {!owner && (
        <div className="seg" role="group" aria-label="정렬">
          {SORTS.map(([key, label]) => (
            <button key={key} aria-pressed={sort === key} onClick={() => setParams({ sort: key })}>{label}</button>
          ))}
        </div>
      )}

      {list === null && <p className="muted">불러오는 중…</p>}
      {list?.length === 0 && (
        <p className="muted empty">
          {mine ? '아직 만든 컬렉션이 없어요. 위의 "새 컬렉션 만들기"나 장소 상세의 "담기"로 시작해 보세요.' : '아직 공개된 컬렉션이 없어요.'}
        </p>
      )}
      {list?.length > 0 && <div className="coll-grid">{list.map((c) => <CollectionCard key={c.id} collection={c} />)}</div>}
    </section>
  )
}
