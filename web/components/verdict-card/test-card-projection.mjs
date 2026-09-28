/**
 * Projection tests for the verdict card (P17). Runs with plain `node --test`
 * (Node >= 23.6 strips types from the imported .ts modules natively):
 *
 *   npm run test:card
 *
 * Pure-JS on purpose: this file is not part of the Next bundle and is excluded
 * from tsc (tsconfig only includes ts/tsx). Coverage: null-metric rendering,
 * refusal panel, neighborhood pseudo-robustness, preview contract, comparison
 * projection, and projection determinism.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { CARD_FIXTURES } from "./card-fixtures.ts";
import {
  AUTHORITY_FOOTER_ZH,
  buildVerdictCardPreview,
  DISPOSITION_BADGES,
  EVIDENCE_STATUS_BADGES,
  projectVerdictCard,
  projectVerdictComparison,
  REFUSED_DISPOSITION_BADGE,
} from "./card-projection.ts";

/** Collect every MetricValue-shaped object in a verdict (metrics + comparisons). */
function collectMetricValues(verdict) {
  const found = [verdict.metrics];
  for (const comparison of verdict.comparisons) {
    found.push(comparison.metrics);
  }
  return found.flatMap((metrics) =>
    Object.entries(metrics)
      .filter(([key]) => key !== "trade_count" && key !== "sample_warning")
      .map(([, metric]) => metric),
  );
}

test("label vocabulary covers the two-layer verdict exactly", () => {
  assert.deepEqual(Object.values(EVIDENCE_STATUS_BADGES).map((badge) => badge.labelZh), [
    "有效",
    "受限",
    "证据不足",
    "无效",
  ]);
  assert.deepEqual(Object.values(DISPOSITION_BADGES).map((badge) => badge.labelZh), [
    "观察",
    "改造",
    "放弃当前修订",
  ]);
  assert.equal(REFUSED_DISPOSITION_BADGE.labelZh, "暂不判断");
});

test("fixtures satisfy the frozen contract invariants (null+reason, pseudo-robust note)", () => {
  for (const [key, verdict] of Object.entries(CARD_FIXTURES)) {
    assert.equal(verdict.schema_version, 1, key);
    assert.equal(verdict.execution_authority, "none", key);
    for (const metric of collectMetricValues(verdict)) {
      if (metric.value !== null) {
        assert.equal(metric.reason, null, `${key}: valued metric must not carry a reason`);
      } else {
        assert.ok(
          typeof metric.reason === "string" && metric.reason.trim() !== "",
          `${key}: null metric must carry a non-empty reason`,
        );
      }
    }
    const hasInactive = verdict.neighborhood.grid.some((point) => !point.param_activated);
    if (hasInactive) {
      assert.ok(
        typeof verdict.neighborhood.pseudo_robust_note === "string" &&
          verdict.neighborhood.pseudo_robust_note.trim() !== "",
        `${key}: inactive param requires pseudo_robust_note`,
      );
    }
  }
});

test("null metrics render the reason, never 0", () => {
  for (const [key, verdict] of Object.entries(CARD_FIXTURES)) {
    const vm = projectVerdictCard(verdict);
    const rowGroups = [vm.metricsRows, ...vm.comparisons.map((comparison) => comparison.rows)];
    for (const rows of rowGroups) {
      for (const row of rows) {
        if (row.isNull) {
          assert.ok(
            row.display.startsWith("不可算"),
            `${key}/${row.key}: null metric must render 不可算, got ${row.display}`,
          );
          assert.doesNotMatch(
            row.display,
            /^-?0([.,]0+)*(%|×)?$/,
            `${key}/${row.key}: null metric must never render as 0`,
          );
        } else {
          assert.match(row.display, /^-?\d/, `${key}/${row.key}: valued metric renders a number`);
        }
      }
    }
  }
});

test("insufficient zero-trades fixture maps null reasons to Chinese labels", () => {
  const vm = projectVerdictCard(CARD_FIXTURES["insufficient-zero-trades"]);
  const winRate = vm.metricsRows.find((row) => row.key === "win_rate");
  const avgWin = vm.metricsRows.find((row) => row.key === "avg_win");
  assert.ok(winRate.isNull);
  assert.ok(winRate.display.includes("分母为零"));
  assert.ok(avgWin.isNull);
  assert.ok(avgWin.display.includes("没有闭合交易"));
  assert.equal(vm.tradeCountDisplay, "0 笔");
  assert.ok(vm.summaryText.includes("不能由 0 胜率推导失败"));
});

test("insufficient and invalid verdicts get a refusal panel; others do not", () => {
  for (const key of ["insufficient-zero-trades", "invalid"]) {
    const vm = projectVerdictCard(CARD_FIXTURES[key]);
    assert.ok(vm.refusal, `${key} must refuse`);
    assert.ok(vm.refusal.blockersZh.length >= 1, `${key} must list blockers`);
    assert.equal(vm.dispositionBadge, null, `${key} has no disposition badge`);
  }
  for (const key of ["valid-observe", "limited-redesign", "param-not-activated"]) {
    assert.equal(projectVerdictCard(CARD_FIXTURES[key]).refusal, null, `${key} must not refuse`);
  }
});

test("neighborhood pseudo-robustness is surfaced when a param never activated", () => {
  const vm = projectVerdictCard(CARD_FIXTURES["param-not-activated"]);
  assert.equal(vm.neighborhood.hasInactiveParams, true);
  assert.ok(vm.neighborhood.pseudoRobustNote && vm.neighborhood.pseudoRobustNote.length > 0);
  const inactiveRow = vm.neighborhood.rows.find((row) => !row.paramActivated);
  assert.ok(inactiveRow, "inactive grid point appears as a row");
  assert.equal(inactiveRow.netPnlDisplay, "未记录");

  const clean = projectVerdictCard(CARD_FIXTURES["valid-observe"]).neighborhood;
  assert.equal(clean.hasInactiveParams, false);
  assert.equal(clean.pseudoRobustNote, null);
});

test("holdout exposure triggers warning styling only when exposed", () => {
  assert.equal(projectVerdictCard(CARD_FIXTURES["valid-observe"]).holdout.exposedWarning, false);
  assert.equal(projectVerdictCard(CARD_FIXTURES["limited-redesign"]).holdout.exposedWarning, true);
});

test("first-screen preview matches the P15 VerdictCardPreview contract", () => {
  const preview = buildVerdictCardPreview(CARD_FIXTURES["valid-observe"]);
  assert.deepEqual(Object.keys(preview).sort(), [
    "conclusionZh",
    "keyEvidenceZh",
    "mainLimitationZh",
    "nextStepZh",
  ]);
  for (const value of Object.values(preview)) {
    assert.equal(typeof value, "string");
    assert.ok(value.length > 0);
  }
  const vm = projectVerdictCard(CARD_FIXTURES["valid-observe"]);
  assert.equal(preview.conclusionZh, vm.summaryText);
  assert.equal(preview.keyEvidenceZh, vm.keyEvidenceText);
  assert.equal(preview.mainLimitationZh, vm.mainLimitations[0]);
  assert.ok(preview.nextStepZh.startsWith("【"));
});

test("summary text templates per disposition", () => {
  assert.ok(
    projectVerdictCard(CARD_FIXTURES["valid-observe"]).summaryText.includes("建议观察"),
  );
  assert.ok(
    projectVerdictCard(CARD_FIXTURES["limited-redesign"]).summaryText.includes("建议改造"),
  );
  assert.ok(projectVerdictCard(CARD_FIXTURES["insufficient-zero-trades"]).summaryText.includes("拒绝判断"));
  assert.ok(projectVerdictCard(CARD_FIXTURES["invalid"]).summaryText.includes("拒绝判断"));

  const retire = {
    ...CARD_FIXTURES["valid-observe"],
    disposition: "retire_current_revision",
    reason_codes: ["underperform_both_baselines"],
  };
  assert.ok(projectVerdictCard(retire).summaryText.includes("放弃当前修订"));
});

test("authority footer is the fixed no-trading-permission line", () => {
  assert.ok(AUTHORITY_FOOTER_ZH.includes("无任何交易权限"));
  for (const verdict of Object.values(CARD_FIXTURES)) {
    assert.equal(projectVerdictCard(verdict).authorityFooterZh, AUTHORITY_FOOTER_ZH);
  }
});

test("key evidence uses the hold comparison and states the funding-counted note", () => {
  const text = projectVerdictCard(CARD_FIXTURES["valid-observe"]).keyEvidenceText;
  assert.ok(text.includes("持有同币种基准"));
  assert.ok(text.includes("Funding payments are counted"));
});

test("comparison projection: spec_hash equality drives the param diff summary", () => {
  const a = CARD_FIXTURES["valid-observe"];
  const b = CARD_FIXTURES["limited-redesign"];
  assert.equal(a.spec_hash, b.spec_hash, "fixtures share spec_hash by default");
  const same = projectVerdictComparison(a, b);
  assert.equal(same.paramDiff.same, true);
  assert.ok(same.paramDiff.summaryZh.includes("一致"));

  const different = projectVerdictComparison(a, {
    ...b,
    spec_hash: `f${b.spec_hash.slice(1)}`,
  });
  assert.equal(different.paramDiff.same, false);
  assert.ok(different.paramDiff.summaryZh.includes("不同"));
});

test("comparison projection: cells, deltas and null handling", () => {
  const comparison = projectVerdictComparison(
    CARD_FIXTURES["valid-observe"],
    CARD_FIXTURES["insufficient-zero-trades"],
  );
  const tradeRow = comparison.rows.find((row) => row.key === "trade_count");
  assert.equal(tradeRow.a.display, "46 笔");
  assert.equal(tradeRow.b.display, "0 笔");
  assert.equal(tradeRow.deltaDisplay, "+46.0");

  const winRow = comparison.rows.find((row) => row.key === "win_rate");
  assert.equal(winRow.a.isNull, false);
  assert.equal(winRow.b.isNull, true);
  assert.equal(winRow.deltaDisplay, null, "no delta when one side is null");
});

test("verdicts without joined evidence sections project with empty evidence blocks", () => {
  // The wire verdict (GET /api/verdicts/{run_id}) carries no time/symbol
  // slices, neighborhood, holdout or stress; those live in the evidence
  // artifact. Projection must tolerate their absence without crashing.
  const wire = { ...CARD_FIXTURES["valid-observe"] };
  delete wire.time_slices;
  delete wire.symbol_slices;
  delete wire.neighborhood;
  delete wire.holdout;
  delete wire.stress;
  const vm = projectVerdictCard(wire);
  assert.deepEqual(vm.timeSlices, []);
  assert.deepEqual(vm.symbolSlices, []);
  assert.equal(vm.neighborhood, null);
  assert.equal(vm.holdout, null);
  assert.deepEqual(vm.stress, []);
  assert.equal(vm.refusal, null);
  assert.ok(vm.summaryText.includes("建议观察"));
});

test("projection is deterministic (same verdict -> identical view model)", () => {
  for (const [key, verdict] of Object.entries(CARD_FIXTURES)) {
    const first = JSON.stringify(projectVerdictCard(verdict));
    const second = JSON.stringify(projectVerdictCard(verdict));
    assert.equal(first, second, key);
    assert.ok(!first.includes("undefined"), `${key}: no undefined leaked into projection`);
  }
  const comparison = JSON.stringify(
    projectVerdictComparison(CARD_FIXTURES["valid-observe"], CARD_FIXTURES["limited-redesign"]),
  );
  assert.equal(
    comparison,
    JSON.stringify(
      projectVerdictComparison(CARD_FIXTURES["valid-observe"], CARD_FIXTURES["limited-redesign"]),
    ),
  );
});
