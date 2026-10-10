import {useState} from "react";
import type {FormEvent} from "react";
import {auth} from "../../services/api";
import {ServerSettingsModal} from "./ServerSettingsModal";

type Mode = "login" | "register" | "worker";
export function LoginScreen({onLoggedIn}: {onLoggedIn: (role: string) => void}) {
  const [entry, setEntry] = useState<"admin" | "worker">("admin");
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [siteName, setSiteName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const changeMode = (next: Mode) => {
    setMode(next); setPassword(""); setPasswordConfirm(""); setError(""); setAvailable(null);
  };
  const selectEntry = (next: "admin" | "worker") => {
    setEntry(next); setUsername(""); setInviteCode(""); changeMode("login");
  };
  const checkUsername = async () => {
    try {
      const result = await auth.usernameAvailable(username.trim());
      setAvailable(result.available);
      if (!result.available) setError(result.reason ?? "이미 사용 중인 ID입니다.");
      return result.available;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "서버 연결을 확인하세요.");
      return false;
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true); setError("");
    try {
      if (mode !== "login") {
        if (password !== passwordConfirm) {setError("비밀번호 확인이 일치하지 않습니다."); return;}
        if (!(await checkUsername())) return;
      }
      const session = mode === "register"
        ? await auth.register(username, password, siteName)
        : mode === "worker"
          ? await auth.signup(username, password, inviteCode).then(() => auth.login(username, password))
          : await auth.login(username, password);
      if ((session.role === "worker") !== (entry === "worker")) {
        await auth.logout();
        setError(entry === "worker" ? "근로자 계정으로 로그인하세요." : "관리자 계정으로 로그인하세요.");
        return;
      }
      onLoggedIn(session.role);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "요청을 완료하지 못했습니다.");
    } finally {setSubmitting(false);}
  };
  return <main className="admin-login-screen">
    <section className="admin-login-card">
      <button className="admin-login-settings" type="button" onClick={() => setSettingsOpen(true)} aria-label="관제 서버 설정">⚙</button>
      <div className="admin-login-mark">H</div>
      <span className="admin-login-eyebrow">HANMIR SMART SAFETY</span>
      <h1>{mode === "login" ? "로그인" : mode === "register" ? "관리자 회원가입" : "근로자 회원가입"}</h1>
      <p>{mode === "login" ? "계정 종류를 선택하고 로그인하세요." : mode === "register" ? "회사·현장 계정을 만들면 독립된 관제 공간이 생성됩니다." : "관리자가 전달한 초대 코드로 내 안전 계정을 만드세요."}</p>
      <div className="login-role-tabs" role="tablist" aria-label="로그인 종류 선택">
        <button type="button" role="tab" aria-selected={entry === "admin"} className={entry === "admin" ? "active" : ""} onClick={() => selectEntry("admin")}>관리자 로그인</button>
        <button type="button" role="tab" aria-selected={entry === "worker"} className={entry === "worker" ? "active" : ""} onClick={() => selectEntry("worker")}>근로자 로그인</button>
      </div>
      <form onSubmit={submit}>
        {mode === "register" && <label>회사 또는 현장명 <span className="admin-optional-label">(선택)</span><input value={siteName} onChange={event => setSiteName(event.target.value)} autoComplete="organization" maxLength={100} placeholder="비워두면 ID로 생성됩니다" /></label>}
        <label>ID <span className="admin-id-field"><input value={username} onChange={event => {setUsername(event.target.value); setAvailable(null);}} autoComplete="username" autoCapitalize="none" autoCorrect="off" minLength={mode === "login" ? undefined : 4} maxLength={30} required placeholder="ID" />{mode !== "login" && <button className="admin-id-check" type="button" onClick={() => void checkUsername()}>중복 확인</button>}</span>{mode !== "login" && available === true && <em className="admin-id-status available">사용 가능한 ID입니다.</em>}</label>
        <label>비밀번호<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={event => setPassword(event.target.value)} minLength={mode === "worker" ? 8 : mode === "register" ? 4 : undefined} maxLength={72} required placeholder={mode === "worker" ? "8자 이상 비밀번호" : "비밀번호"} /></label>
        {mode !== "login" && <label>비밀번호 확인<input type="password" autoComplete="new-password" value={passwordConfirm} onChange={event => setPasswordConfirm(event.target.value)} required placeholder="비밀번호를 다시 입력하세요" /></label>}
        {mode === "worker" && <label>초대 코드<input value={inviteCode} onChange={event => setInviteCode(event.target.value)} autoCapitalize="none" autoCorrect="off" required placeholder="관리자에게 받은 코드" /></label>}
        {error && <div className="admin-login-error" role="alert">{error}</div>}
        <button disabled={submitting} type="submit">{submitting ? "처리 중…" : mode === "login" ? "로그인" : "회원가입 후 시작"}</button>
      </form>
      {mode === "login" ? <button className="admin-signup-link" onClick={() => changeMode(entry === "admin" ? "register" : "worker")}>{entry === "admin" ? "관리자" : "근로자"} 회원가입</button> : <button className="admin-signup-link" onClick={() => changeMode("login")}>로그인으로 돌아가기</button>}
      <span className="admin-login-version">v1.8 · 관리자·근로자 통합 앱</span>
    </section>
    <ServerSettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} onSaved={() => setSettingsOpen(false)} />
  </main>;
}
