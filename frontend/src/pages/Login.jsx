import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorText } from '../api'
import { useAuth } from '../auth'
import KakaoButton from '../components/KakaoButton'
import { Field } from './AuthForm'

export default function Login() {
  const { login, expired } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(form.username, form.password)
      navigate('/')
    } catch (err) {
      setError(err.status === 401 ? '아이디 또는 비밀번호가 맞지 않아요.' : errorText(err, '로그인하지 못했어요. 잠시 후 다시 시도하세요.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="auth" onSubmit={onSubmit}>
      <h1>로그인</h1>
      {expired && <p className="muted" role="status">로그인이 만료됐어요. 다시 로그인해 주세요.</p>}
      <Field label="아이디" name="username" value={form.username} onChange={onChange} autoComplete="username" />
      <Field label="비밀번호" name="password" type="password" value={form.password} onChange={onChange} autoComplete="current-password" />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn primary" disabled={busy}>{busy ? '로그인하는 중…' : '로그인'}</button>
      <div className="divider"><span>또는</span></div>
      <KakaoButton />
      <p className="muted">처음이세요? <Link to="/signup">회원가입</Link></p>
    </form>
  )
}
