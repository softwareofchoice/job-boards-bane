import { useQuery } from "@tanstack/react-query";
import { useRef, useState, type FocusEvent, type PointerEvent } from "react";

import { getStatusFlow, trackerKeys, type FlowPath } from "./api";
import {
  AXES,
  categoryLabel,
  describePath,
  layoutFlow,
  OUTCOMES,
  outcomeOf,
  type Band,
  type NodeBox,
} from "./status";

// Geometry in viewBox units; the SVG scales to its container's width.
const WIDTH = 760;
const PLOT_HEIGHT = 230;
const TOP = 40;
const BOTTOM = 8;
const NODE_WIDTH = 12;
// Room between categories for the middle axis's labels, which sit above their bars.
const GAP = 20;
const AXIS_X = [16, 300, 584];
const LABEL_GAP = 8;
const LINE = 15; // minimum distance between label baselines on one axis

interface Tip {
  path: FlowPath;
  x: number;
  y: number;
}

const TIP_WIDTH = 240;

/** Keep the tooltip inside the frame. */
function clampX(x: number, width: number): number {
  return Math.max(0, Math.min(x, width - TIP_WIDTH - 12));
}

function plural(n: number): string {
  return `${n} application${n === 1 ? "" : "s"}`;
}

/** One ribbon through all three axes: top edge left to right, bottom edge back. */
function ribbonPath(bands: Band[]): string {
  const xs = AXIS_X.map((x) => [x, x + NODE_WIDTH] as const);
  const b = bands.map((band) => ({ y0: band.y0 + TOP, y1: band.y1 + TOP }));
  const curve = (xa: number, ya: number, xb: number, yb: number) => {
    const mid = (xa + xb) / 2;
    return `C ${mid} ${ya} ${mid} ${yb} ${xb} ${yb}`;
  };
  const [a, m, z] = [b[0]!, b[1]!, b[2]!];
  const [x0, x1, x2] = [xs[0]!, xs[1]!, xs[2]!];
  return [
    `M ${x0[1]} ${a.y0}`,
    curve(x0[1], a.y0, x1[0], m.y0),
    `L ${x1[1]} ${m.y0}`,
    curve(x1[1], m.y0, x2[0], z.y0),
    `L ${x2[0]} ${z.y1}`,
    curve(x2[0], z.y1, x1[1], m.y1),
    `L ${x1[0]} ${m.y1}`,
    curve(x1[0], m.y1, x0[1], a.y1),
    "Z",
  ].join(" ");
}

/**
 * Where an axis's labels go. The first axis has one category, named in its title. The middle
 * axis is crossed by ribbons on both sides, so its labels sit in the gap above each bar. The
 * last axis has free space to its right, so labels sit beside the bars, pushed apart so they
 * never overlap.
 */
function labelPositions(axis: number, nodes: NodeBox[]): { x: number; y: number }[] {
  if (axis === 0) return [];
  if (axis === 1) {
    return nodes.map((node) => ({ x: AXIS_X[1]!, y: TOP + node.y0 - 6 }));
  }
  return labelYs(nodes).map((y) => ({ x: AXIS_X[2]! + NODE_WIDTH + LABEL_GAP, y }));
}

/** Label positions beside one axis's nodes, pushed apart so they never overlap. */
function labelYs(nodes: NodeBox[]): number[] {
  const ys: number[] = [];
  nodes.forEach((node, i) => {
    const centre = TOP + (node.y0 + node.y1) / 2 + 4;
    const prev = i > 0 ? ys[i - 1]! : -Infinity;
    ys.push(Math.max(centre, prev + LINE));
  });
  return ys;
}

/** How applications moved between statuses, as a parallel sets plot (TRK-5). */
export function StatusFlowPlot() {
  const { data } = useQuery({ queryKey: trackerKeys.flow, queryFn: getStatusFlow });
  const [tip, setTip] = useState<Tip | null>(null);
  const [showTable, setShowTable] = useState(false);
  const frame = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);

  if (!data || data.total === 0) return null;

  const layout = layoutFlow(data.paths, PLOT_HEIGHT, GAP);
  const nodesByAxis = AXES.map((_, axis) => layout.nodes.filter((n) => n.axis === axis));
  const height = TOP + PLOT_HEIGHT + BOTTOM;

  function showAtPointer(path: FlowPath, e: PointerEvent) {
    const box = frame.current?.getBoundingClientRect();
    if (!box) return;
    setTip({ path, x: clampX(e.clientX - box.left, box.width), y: e.clientY - box.top });
  }

  function showAtRibbon(path: FlowPath, bands: Band[], e: FocusEvent) {
    const box = frame.current?.getBoundingClientRect();
    const plot = svg.current?.getBoundingClientRect();
    if (!box || !plot) return;
    const scale = plot.width / WIDTH;
    const middle = bands[1]!;
    setTip({
      path,
      x: clampX(plot.left - box.left + (AXIS_X[1]! + NODE_WIDTH / 2) * scale, box.width),
      y: plot.top - box.top + (TOP + (middle.y0 + middle.y1) / 2) * scale,
    });
    e.stopPropagation();
  }

  return (
    <section className="status-flow" aria-labelledby="status-flow-heading">
      <div className="results-header">
        <h2 id="status-flow-heading">
          Status flow <span className="muted">· {plural(data.total)}</span>
        </h2>
        <button
          type="button"
          className="button button-small"
          aria-pressed={showTable}
          onClick={() => setShowTable((v) => !v)}
        >
          {showTable ? "Show as chart" : "Show as table"}
        </button>
      </div>

      {showTable ? (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Path</th>
              <th scope="col">Outcome</th>
              <th scope="col" className="numeric">
                Applications
              </th>
            </tr>
          </thead>
          <tbody>
            {data.paths.map((path) => (
              <tr key={path.statuses.join("-")}>
                <td>{describePath(path)}</td>
                <td>{OUTCOMES.find(([o]) => o === outcomeOf(path))![1]}</td>
                <td className="numeric">{path.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="flow-frame" ref={frame} onPointerLeave={() => setTip(null)}>
          <ul className="flow-legend" aria-label="Ribbon colour: where applications ended up">
            {OUTCOMES.map(([outcome, label]) => (
              <li key={outcome}>
                <span className={`flow-key flow-${outcome}`} aria-hidden="true" />
                {label}
              </li>
            ))}
          </ul>
          <svg
            ref={svg}
            className="flow-plot"
            viewBox={`0 0 ${WIDTH} ${height}`}
            role="group"
            aria-label={`Status flow of ${plural(data.total)}`}
          >
            {AXES.map((title, axis) => (
              <text key={title} className="flow-axis-title" x={AXIS_X[axis]} y={14}>
                {title}
                {axis === 0 ? <tspan className="flow-count"> {data.total}</tspan> : null}
              </text>
            ))}
            <g className={tip ? "flow-ribbons flow-ribbons-active" : "flow-ribbons"}>
              {layout.ribbons.map(({ path, bands }) => (
                <path
                  key={path.statuses.join("-")}
                  className={`flow-ribbon flow-${outcomeOf(path)}${
                    tip?.path === path ? " flow-ribbon-hover" : ""
                  }`}
                  d={ribbonPath(bands)}
                  tabIndex={0}
                  role="img"
                  aria-label={`${describePath(path)}: ${plural(path.count)}`}
                  onPointerMove={(e) => showAtPointer(path, e)}
                  onFocus={(e) => showAtRibbon(path, bands, e)}
                  onBlur={() => setTip(null)}
                />
              ))}
            </g>
            {nodesByAxis.map((nodes, axis) => {
              const labels = labelPositions(axis, nodes);
              return nodes.map((node, i) => (
                <g key={`${node.axis}-${node.status}`} className="flow-node">
                  <rect
                    x={AXIS_X[node.axis]}
                    y={TOP + node.y0}
                    width={NODE_WIDTH}
                    height={Math.max(node.y1 - node.y0, 1)}
                    rx={2}
                  />
                  {labels[i] ? (
                    <text className="flow-label" x={labels[i].x} y={labels[i].y}>
                      {categoryLabel(node.axis, node.status)}
                      <tspan className="flow-count"> {node.count}</tspan>
                    </text>
                  ) : null}
                </g>
              ));
            })}
          </svg>
          {tip ? (
            <div
              className="flow-tooltip"
              role="status"
              style={{ left: tip.x + 12, top: tip.y + 12 }}
            >
              <strong>{plural(tip.path.count)}</strong>
              <span>{describePath(tip.path)}</span>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
