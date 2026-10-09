import type { Status } from "./api";
import { STATUS_LABELS } from "./status";

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`status-badge status-${status}`}>{STATUS_LABELS[status]}</span>;
}
