import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import KakaoButton from '../components/KakaoButton'
import { Field } from './AuthForm'

export default function Signup() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', nickname: '', password: '' })
  const [errors, setErrors] = useState(null)
  const [busy, setBusy] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setErrors(null)
    try {
      await signup(form)
      navigate('/')
    } catch (err) {
      // 400 이면 서버가 {필드: [메시지]} 형태로 이유를 알려준다
      setErrors(err.status === 400 ? err.data : { form: ['가입하지 못했어요. 잠시 후 다시 시도하세요.'] })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="auth" onSubmit={onSubmit}>
      <h1>회원가입</h1>
      <Field label="아이디" name="username" value={form.username} onChange={onChange} errors={errors} autoComplete="username" />
      <Field label="닉네임" name="nickname" value={form.nickname} onChange={onChange} errors={errors} autoComplete="nickname" />
      <Field label="비밀번호 (8자 이상)" name="password" type="password" value={form.password} onChange={onChange} errors={errors} autoComplete="new-password" />
      {errors?.form && <p className="error" role="alert">{errors.form}</p>}
      <button className="btn primary" disabled={busy}>{busy ? '가입하는 중…' : '가입하기'}</button>
      <div className="divider"><span>또는</span></div>
      <KakaoButton />
      <p className="muted">이미 계정이 있으세요? <Link to="/login">로그인</Link></p>
    </form>
  )
}
