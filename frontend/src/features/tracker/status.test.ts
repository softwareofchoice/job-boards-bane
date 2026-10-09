import { makeFlow } from "./fixtures";
import { categoryLabel, describePath, layoutFlow, outcomeOf } from "./status";

describe("status helpers", () => {
  it("names categories by what they mean on each axis", () => {
    expect(categoryLabel(0, "applied")).toBe("Applied");
    expect(categoryLabel(1, "applied")).toBe("No response yet");
    expect(categoryLabel(2, "interviewing")).toBe("Still interviewing");
    expect(categoryLabel(2, "offer")).toBe("Offer");
  });

  it("describes paths without repeating carried-forward statuses", () => {
    const [offer, waiting, interviewing, rejected] = makeFlow().paths;
    expect(describePath(offer!)).toBe("Applied → Interviewing → Offer");
    expect(describePath(waiting!)).toBe("Applied (no response yet)");
    expect(describePath(interviewing!)).toBe("Applied → Interviewing (still interviewing)");
    expect(describePath(rejected!)).toBe("Applied → Rejected");
    expect([offer, waiting, rejected].map((p) => outcomeOf(p!))).toEqual([
      "offer",
      "open",
      "rejected",
    ]);
  });
});

describe("layoutFlow", () => {
  const flow = makeFlow();
  const layout = layoutFlow(flow.paths, 210, 10);

  it("sizes each category by its count, stacked with gaps", () => {
    const axis1 = layout.nodes.filter((n) => n.axis === 1);
    expect(axis1.map((n) => [n.status, n.count])).toEqual([
      ["interviewing", 4],
      ["applied", 2],
      ["rejected", 1],
    ]);
    // 210 high, 3 categories at most on axis 1 but 4 on axis 2: 30 of gaps, 180 for 7.
    const unit = 180 / 7;
    expect(axis1[0]!.y1 - axis1[0]!.y0).toBeCloseTo(4 * unit);
    expect(axis1[1]!.y0 - axis1[0]!.y1).toBeCloseTo(10);
    expect(layout.nodes.filter((n) => n.axis === 0)).toEqual([
      { axis: 0, status: "applied", count: 7, y0: 0, y1: 7 * unit },
    ]);
  });

  it("gives every path a band inside its category at every axis", () => {
    for (const ribbon of layout.ribbons) {
      expect(ribbon.bands).toHaveLength(3);
      ribbon.bands.forEach((band, axis) => {
        const node = layout.nodes.find(
          (n) => n.axis === axis && n.status === ribbon.path.statuses[axis],
        )!;
        expect(band.y0).toBeGreaterThanOrEqual(node.y0 - 1e-9);
        expect(band.y1).toBeLessThanOrEqual(node.y1 + 1e-9);
        expect(band.y1 - band.y0).toBeCloseTo((ribbon.path.count * 180) / 7);
      });
    }
  });

  it("orders bands so ribbons don't cross inside a node", () => {
    const byPath = (key: string) =>
      layout.ribbons.find((r) => r.path.statuses.join() === key)!.bands;
    // Inside "Interviewing" on axis 1, the path to Offer sits above the one still interviewing.
    expect(byPath("applied,interviewing,offer")[1]!.y0).toBeLessThan(
      byPath("applied,interviewing,interviewing")[1]!.y0,
    );
  });

  it("is empty without applications", () => {
    expect(layoutFlow([], 200, 10)).toEqual({ nodes: [], ribbons: [] });
  });
});
