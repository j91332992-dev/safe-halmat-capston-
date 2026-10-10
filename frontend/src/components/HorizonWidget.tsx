// Adapted from Horizon UI Card and Widget (MIT). See vendor/horizon/LICENSE.md.
import type {ReactNode} from "react";
interface Props {
  icon: ReactNode;
  title: string;
  value: ReactNode;
  footer: ReactNode;
  className?: string;
  onClick: () => void;
}
export function HorizonWidget({icon, title, value, footer, className = "", onClick}: Props) {
  return <button className={`horizon-card control-kpi ${className}`} onClick={onClick}>
    <div className="horizon-widget-row">
      <div className="horizon-widget-icon" aria-hidden="true">{icon}</div>
      <div className="horizon-widget-content">
        <span className="control-kpi-label">{title}</span>
        <strong>{value}</strong>
      </div>
    </div>
    <div className="control-kpi-footer">{footer}<span aria-hidden="true">↗</span></div>
  </button>;
}
