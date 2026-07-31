interface Props {
  active: boolean;
  activeText?: string;
  inactiveText?: string;
}

export function StatusPill({active, activeText = "정상", inactiveText = "오류"}: Props) {
  return <span className={`status-pill ${active ? "is-active" : "is-inactive"}`}><i />{active ? activeText : inactiveText}</span>;
}

