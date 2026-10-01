import {useState} from "react";
import type {FormEvent} from "react";
import {auth} from "../../services/api";

export function LoginScreen({onLoggedIn}: {onLoggedIn: () => void}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await auth.login(username, password);
      onLoggedIn();
    } catch {
      setError("관리자 ID 또는 비밀번호를 다시 확인하세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="admin-login-screen">
    <section className="admin-login-card">
      <div className="admin-login-mark">H</div>
      <span className="admin-login-eyebrow">HANMIR SAFETY CONTROL</span>
      <h1>관리자 로그인</h1>
      <p>승인된 관리자만 현장 안전관제에 접근할 수 있습니다.</p>
      <form onSubmit={submit}>
        <label>관리자 ID<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} placeholder="관리자 ID" required /></label>
        <label>비밀번호<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="비밀번호" required /></label>
        {error && <div className="admin-login-error">⚠️ {error}</div>}
        <button disabled={submitting} type="submit">{submitting ? "로그인 확인 중" : "로그인"}</button>
      </form>
      <small>무단 접근 시도는 허용되지 않습니다.</small>
    </section>
  </main>;
}
