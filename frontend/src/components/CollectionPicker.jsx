import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import useDismiss from './useDismiss'

// 장소 상세의 "컬렉션에 담기": 내 컬렉션을 눌러 담기·빼기, 새 컬렉션을 만들면서 바로 담기
export default function CollectionPicker({ place }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const box = useRef(null)
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState(null)
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useDismiss(box, open, () => setOpen(false))

  const load = () => apiFetch(`/api/me/collections/?place=${place.id}`).then(setRows).catch(() => setRows([]))

  function toggleOpen() {
    if (!user) return navigate('/login')
    if (!open) load()
    setError('')
    setOpen(!open)
  }

  async function toggle(row) {
    setBusy(true)
    try {
      const res = await apiFetch(`/api/collections/${row.id}/places/${place.id}/`, { method: row.has_place ? 'DELETE' : 'POST' })
      setRows((rs) => rs.map((r) => (r.id === row.id ? { ...r, has_place: res.in_collection, place_count: res.place_count } : r)))
    } catch (err) {
      setError(err.data?.detail ?? '담지 못했어요. 잠시 후 다시 시도하세요.')
    } finally {
      setBusy(false)
    }
  }

  async function create(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const made = await apiFetch('/api/collections/', { method: 'POST', body: { title } })
      await apiFetch(`/api/collections/${made.id}/places/${place.id}/`, { method: 'POST' })
      setTitle('')
      await load()
    } catch (err) {
      setError(err.data?.detail || Object.values(err.data ?? {}).flat().join(' ') || '만들지 못했어요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="share" ref={box}>
      <button className="btn" onClick={toggleOpen} aria-expanded={open} aria-haspopup="menu">
        <svg className="share-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 20.5V5.5A1.5 1.5 0 0 1 7.5 4h9A1.5 1.5 0 0 1 18 5.5v15l-6-4z" /><path d="M12 8v5M9.5 10.5h5" /></svg>
        <span className="share-label">담기</span>
      </button>
      {open && (
        <div className="share-menu collect-menu" role="menu" aria-label="컬렉션에 담기">
          <p className="menu-title">컬렉션에 담기</p>
          {rows === null && <p className="muted small menu-note">불러오는 중…</p>}
          {rows?.length === 0 && <p className="muted small menu-note">아직 컬렉션이 없어요. 이름을 정해 첫 컬렉션을 만들어 보세요.</p>}
          {rows?.map((r) => (
            <button key={r.id} role="menuitemcheckbox" aria-checked={r.has_place} onClick={() => toggle(r)} disabled={busy}>
              <span className={`check${r.has_place ? ' on' : ''}`} aria-hidden="true">✓</span>
              <span className="collect-title">{r.title}</span>
              <em>{r.place_count}</em>
            </button>
          ))}
          <form className="collect-new" onSubmit={create}>
            <label className="sr-only" htmlFor="new-collection">새 컬렉션 이름</label>
            <input id="new-collection" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={40} placeholder="새 컬렉션 (예: 카공하기 좋은 카페)" />
            <button className="btn dark small" disabled={busy || !title.trim()}>만들기</button>
          </form>
          {error && <p className="error small menu-note" role="alert">{error}</p>}
          <Link to={`/collections?user=${user.id}`} className="menu-link">내 컬렉션 보기</Link>
        </div>
      )}
    </div>
  )
}
