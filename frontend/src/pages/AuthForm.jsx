// 로그인·회원가입이 같이 쓰는 입력칸. 서버가 보낸 필드별 에러를 칸 아래에 보여준다
export function Field({ label, name, type = 'text', value, onChange, errors, autoComplete }) {
  const messages = errors?.[name]
  return (
    <label className="field">
      <span>{label}</span>
      <input
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        autoComplete={autoComplete}
        aria-invalid={Boolean(messages)}
        required
      />
      {messages && <small className="error">{messages.join(' ')}</small>}
    </label>
  )
}
