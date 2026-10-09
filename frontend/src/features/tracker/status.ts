/** Status labels and the parallel sets layout for the status flow plot (TRK-4, TRK-5). */
import type { FlowPath, Status } from "./api";

export const STATUS_LABELS: Record<Status, string> = {
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
};

export const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as Status[]).map(
  (s) => [s, STATUS_LABELS[s]] as const,
);

/** Button text for moving to a status. */
export const MOVE_LABELS: Record<Status, string> = {
  applied: "Back to Applied",
  interviewing: "Got an interview",
  offer: "Got an offer",
  rejected: "Rejected",
};

export const AXES = ["Applied", "After applying", "Outcome"] as const;

/** Categories on each axis, top to bottom. Order keeps ribbons from crossing. */
export const AXIS_ORDER: Status[][] = [
  ["applied"],
  ["interviewing", "applied", "rejected"],
  ["offer", "interviewing", "applied", "rejected"],
];

/** What a status means at a given axis: a path that stopped early carries its status forward. */
export function categoryLabel(axis: number, status: Status): string {
  if (axis > 0 && status === "applied") return "No response yet";
  if (axis === 2 && status === "interviewing") return "Still interviewing";
  return STATUS_LABELS[status];
}

export type Outcome = "offer" | "rejected" | "open";

export const OUTCOMES: [Outcome, string][] = [
  ["offer", "Offer"],
  ["rejected", "Rejected"],
  ["open", "Still open"],
];

export function outcomeOf(path: FlowPath): Outcome {
  const last = path.statuses[2];
  return last === "offer" || last === "rejected" ? last : "open";
}

/** "Applied → Interviewing → Offer", with a note for paths still open. */
export function describePath(path: FlowPath): string {
  const steps = path.statuses.filter((s, i) => i === 0 || s !== path.statuses[i - 1]);
  const text = steps.map((s) => STATUS_LABELS[s]).join(" → ");
  const last = steps[steps.length - 1];
  if (last === "applied") return `${text} (no response yet)`;
  if (last === "interviewing") return `${text} (still interviewing)`;
  return text;
}

export interface Band {
  y0: number;
  y1: number;
}

export interface NodeBox {
  axis: number;
  status: Status;
  count: number;
  y0: number;
  y1: number;
}

export interface RibbonLayout {
  path: FlowPath;
  bands: Band[]; // one per axis
}

export interface FlowLayout {
  nodes: NodeBox[];
  ribbons: RibbonLayout[];
}

const OUTCOME_ORDER: Record<Outcome, number> = { offer: 0, open: 1, rejected: 2 };

/**
 * Lay out a parallel sets plot: on each axis the categories are stacked (with `gap` between
 * them) and sized by count over `height`; each path takes a band inside the category it passes
 * through at every axis. Bands within a category are ordered by where the paths go next, so
 * ribbons don't cross inside a node.
 */
export function layoutFlow(paths: FlowPath[], height: number, gap: number): FlowLayout {
  const total = paths.reduce((sum, p) => sum + p.count, 0);
  if (total === 0) return { nodes: [], ribbons: [] };
  const maxCategories = Math.max(...AXIS_ORDER.map((order) => order.length));
  const scale = (height - gap * (maxCategories - 1)) / total;

  const nodes: NodeBox[] = [];
  const bands: Band[][] = paths.map(() => []);

  AXIS_ORDER.forEach((order, axis) => {
    let y = 0;
    for (const status of order) {
      const members = paths
        .map((path, index) => ({ path, index }))
        .filter(({ path }) => path.statuses[axis] === status)
        .sort((a, b) => rank(a.path) - rank(b.path));
      const count = members.reduce((sum, m) => sum + m.path.count, 0);
      if (count === 0) continue;
      const y0 = y;
      for (const { path, index } of members) {
        const h = path.count * scale;
        bands[index]![axis] = { y0: y, y1: y + h };
        y += h;
      }
      nodes.push({ axis, status, count, y0, y1: y });
      y += gap;
    }
  });

  return { nodes, ribbons: paths.map((path, i) => ({ path, bands: bands[i]! })) };
}

/** Sort key for a path inside a category: by its later categories, then by outcome. */
function rank(path: FlowPath): number {
  let key = 0;
  for (const axis of [1, 2] as const) {
    key = key * 10 + AXIS_ORDER[axis]!.indexOf(path.statuses[axis]);
  }
  return key * 10 + OUTCOME_ORDER[outcomeOf(path)];
}
