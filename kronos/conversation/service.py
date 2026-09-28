# ruff: noqa: RUF001 -- Chinese user-facing strings use fullwidth punctuation.
"""ConversationService: sessions, deterministic intents, revision lineage (P14).

Pipeline for :meth:`ConversationService.send_message`:

1. persist the user message (SQLite ``conversations.sqlite3``);
2. parse the intent with :func:`kronos.conversation.intents.parse_intent`
   (fully deterministic; see below);
3. route by kind:
   - ``adjust_param`` / ``switch_symbol`` / ``switch_timeframe`` resolved →
     build the CHILD revision (params via
     :func:`kronos.strategy.spec.make_revision`; symbol/timeframe via the
     same content-hash identity rules) → show the DIFF in the assistant
     message → reserve ONE backtest in the round's
     :class:`~kronos.runtime.budget.BudgetLedger` → submit an
     ``evaluate_strategy`` task through the
     :class:`~kronos.runtime.tasks.TaskStore` (idempotency hash =
     canonical payload hash over spec content + session + snapshot policy +
     budget binding ids, so the same logical evaluation reuses the same
     task/artifacts);
   - ``evidence_question`` → read the latest succeeded verdict for the
     session (no new task) and return fact refs;
   - ``ask_verdict`` (default) → answer from the current revision + latest
     verdict (no new task);
   - ``out_of_scope`` → refusal message, never a task;
   - ``needs_clarification`` → one focused question; the half-specified
     adjustment is stored on the session and merged into the next turn.
4. persist the assistant message and return a 202-shaped
   :class:`MessageResult`.

**LLM assist is a later fallback hook, deliberately NOT wired here:** the
deterministic chain must be complete without any model (design section 1).
A future package may wrap step 2: when ``parse_intent`` returns
``needs_clarification``, optionally consult
:class:`kronos.conversation.llm_client.GLMClient` to propose a reading and
ECHO it back for confirmation — the service never lets an LLM produce
parameters silently, and budget reservation for that call belongs to the
same round ledger.

Tool whitelist (spec ``conversation-web``: server-side binding, strict
schema, chat content can never change tool semantics): the registry maps
``ensure_data`` / ``evaluate_strategy`` (submit tasks) and
``compare_runs`` / ``read_evidence`` (read-only) to handlers that validate
every input against the frozen validators (symbol regex, timeframe
literal, ``StrategySpec`` with ``extra="forbid"``, known tool names).
Injection-style payloads fail validation instead of gaining permissions.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from kronos.common.errors import KronosError
from kronos.conversation.intents import (
    ATR_PARAM,
    MULTIPLIER_PARAM,
    ParsedIntent,
    PendingAdjustment,
    parse_intent,
)
from kronos.research.verdict.contracts import BudgetBlock
from kronos.runtime.budget import (
    BudgetExhausted,
    BudgetLedger,
    BudgetLimits,
    BudgetPlan,
)
from kronos.runtime.tasks import TaskStore, canonical_payload_sha256, now_ms
from kronos.strategy.spec import (
    StrategySpec,
    compute_spec_hash,
    derive_revision_id,
    make_revision,
    spec_identity_content,
)

SNAPSHOT_POLICY_ID: Final[str] = "window_90_complete_utc_days"
DEFAULT_ROUND_WALL_CLOCK_S: Final[float] = 1800.0
_ROUND_PREFIX: Final[str] = "conv"

type MessageStatus = Literal[
    "submitted",
    "answered",
    "clarification_needed",
    "refused",
    "budget_exhausted",
]

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    created_at_ms INTEGER NOT NULL,
    pending_json TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    intent_kind   TEXT,
    status        TEXT,
    payload_json  TEXT,
    created_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
CREATE TABLE IF NOT EXISTS current_revision_json (
    session_id    TEXT PRIMARY KEY,
    spec_json     TEXT NOT NULL,
    updated_at_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS holdout_exposure_count (
    session_id    TEXT PRIMARY KEY,
    count         INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL
);
"""


class ConversationError(KronosError):
    """Base class for conversation service failures."""


class SessionNotFoundError(ConversationError):
    """No session exists for the given id."""


class ToolAccessError(ConversationError):
    """A tool name or payload failed the strict whitelist validation."""


class RevisionDiffEntry(BaseModel):
    """One human-readable field change between parent and child revision."""

    model_config = ConfigDict(extra="forbid")

    field: str
    old: str
    new: str


class SessionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    created_at_ms: int
    current_revision_id: str


class MessageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    intent_kind: str | None = None
    status: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at_ms: int


class MessageResult(BaseModel):
    """202-shaped result of one conversation turn."""

    model_config = ConfigDict(extra="forbid")

    message_id: int
    assistant_message_id: int
    session_id: str
    intent_kind: str
    status: MessageStatus
    echo_text: str
    clarification_question: str | None = None
    revision_id: str | None = None
    parent_revision_id: str | None = None
    diff: list[RevisionDiffEntry] = Field(default_factory=list)
    task_id: str | None = None
    task_state: str | None = None
    verdict_refs: list[str] = Field(default_factory=list)


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: SessionInfo
    current_revision: dict[str, Any]
    holdout_exposure_count: int
    messages: list[MessageRecord]


class ConversationService:
    """Owns the conversation SQLite store plus the runtime task/budget stores."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        task_store: TaskStore | None = None,
        budget_ledger: BudgetLedger | None = None,
        budget_limits: BudgetLimits | None = None,
    ) -> None:
        self._dir = Path(state_dir)
        if str(self._dir) != ":memory:":
            self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        db_path = (
            ":memory:" if str(self._dir) == ":memory:" else str(self._dir / "conversations.sqlite3")
        )
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._tasks = task_store or TaskStore(
            ":memory:" if str(self._dir) == ":memory:" else self._dir / "runtime.sqlite3"
        )
        self._budget = budget_ledger or BudgetLedger(
            ":memory:" if str(self._dir) == ":memory:" else self._dir / "budget.sqlite3",
            limits=budget_limits,
        )
        self._tool_registry: dict[str, Any] = {
            "ensure_data": self._tool_ensure_data,
            "evaluate_strategy": self._tool_evaluate_strategy,
            "compare_runs": self._tool_compare_runs,
            "read_evidence": self._tool_read_evidence,
        }

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self._conn.close()
        self._tasks.close()
        self._budget.close()

    @property
    def task_store(self) -> TaskStore:
        return self._tasks

    @property
    def budget_ledger(self) -> BudgetLedger:
        return self._budget

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(self._tool_registry)

    # ------------------------------------------------------------------ sessions

    def create_session(self) -> SessionInfo:
        """Create a session rooted at the default spec revision.

        ``StrategySpec.model_validate({})`` (not ``StrategySpec()``) is
        required here: the frozen after-validators derive the identity fields
        through a model copy, which only takes effect on the
        ``model_validate`` path.
        """
        session_id = uuid.uuid4().hex
        root_spec = StrategySpec.model_validate({})
        ts = now_ms()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions (session_id, created_at_ms, pending_json) VALUES (?, ?, NULL)",
                (session_id, ts),
            )
            self._conn.execute(
                "INSERT INTO current_revision_json (session_id, spec_json, updated_at_ms) "
                "VALUES (?, ?, ?)",
                (session_id, root_spec.model_dump_json(), ts),
            )
        return SessionInfo(
            session_id=session_id,
            created_at_ms=ts,
            current_revision_id=root_spec.strategy_revision_id,
        )

    def current_revision(self, session_id: str) -> StrategySpec:
        row = self._get_session_row(session_id)
        return self._row_to_spec(row)

    def get_session(self, session_id: str) -> SessionDetail:
        row = self._get_session_row(session_id)
        return SessionDetail(
            session=SessionInfo(
                session_id=session_id,
                created_at_ms=int(row["created_at_ms"]),
                current_revision_id=self._row_to_spec(row).strategy_revision_id,
            ),
            current_revision=self._row_to_spec(row).model_dump(mode="json"),
            holdout_exposure_count=self.holdout_exposure_count(session_id),
            messages=self.list_messages(session_id),
        )

    def list_messages(self, session_id: str) -> list[MessageRecord]:
        self._get_session_row(session_id)
        with self._lock:
            rows = (
                self._conn.cursor()
                .execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
                    (session_id,),
                )
                .fetchall()
            )
        return [self._row_to_message(row) for row in rows]

    def mark_holdout_exposed(self, session_id: str) -> int:
        """Count one holdout look-ahead; returns the new exposure count."""
        self._get_session_row(session_id)
        ts = now_ms()
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT count FROM holdout_exposure_count WHERE session_id = ?", (session_id,)
            ).fetchone()
            new_count = (int(row["count"]) if row is not None else 0) + 1
            self._conn.execute(
                "INSERT INTO holdout_exposure_count (session_id, count, updated_at_ms) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET count = excluded.count, "
                "updated_at_ms = excluded.updated_at_ms",
                (session_id, new_count, ts),
            )
        return new_count

    def holdout_exposure_count(self, session_id: str) -> int:
        self._get_session_row(session_id)
        with self._lock:
            row = self._conn.execute(
                "SELECT count FROM holdout_exposure_count WHERE session_id = ?", (session_id,)
            ).fetchone()
        return int(row["count"]) if row is not None else 0

    # ------------------------------------------------------------------ messaging

    def send_message(self, session_id: str, text: str) -> MessageResult:
        """Run one deterministic conversation turn (see module docstring)."""
        row = self._get_session_row(session_id)
        current = self._row_to_spec(row)
        pending = self._row_to_pending(row)
        user_message_id = self._append_message(
            session_id=session_id, role="user", content=text, created_at=now_ms()
        )
        parsed = parse_intent(
            text,
            pending_param=pending.param if pending is not None else None,
            pending_value=pending.value if pending is not None else None,
        )

        if parsed.status == "refused":
            assert parsed.refusal_reason is not None
            result = self._finish_refusal(session_id, user_message_id, parsed)
        elif parsed.status == "needs_clarification":
            result = self._finish_clarification(session_id, user_message_id, parsed)
        elif parsed.kind == "adjust_param" and parsed.param_overrides:
            result = self._finish_revision_change(
                session_id, user_message_id, current, parsed, param_overrides=parsed.param_overrides
            )
        elif parsed.kind == "switch_symbol" and parsed.symbol is not None:
            result = self._finish_revision_change(
                session_id, user_message_id, current, parsed, symbols=[parsed.symbol]
            )
        elif parsed.kind == "switch_timeframe" and parsed.timeframe is not None:
            result = self._finish_revision_change(
                session_id, user_message_id, current, parsed, timeframe=parsed.timeframe
            )
        elif parsed.kind == "evidence_question":
            result = self._finish_evidence_question(session_id, user_message_id, current)
        else:
            result = self._finish_ask_verdict(session_id, user_message_id, current)
        return result

    # ------------------------------------------------------------------ turn endings

    def _finish_refusal(
        self, session_id: str, user_message_id: int, parsed: ParsedIntent
    ) -> MessageResult:
        assert parsed.refusal_reason is not None
        self._set_pending(session_id, None)
        assistant_id = self._append_assistant(
            session_id=session_id,
            content=parsed.echo_text,
            intent_kind=parsed.kind,
            status="refused",
            payload={"refusal_reason": parsed.refusal_reason},
        )
        return MessageResult(
            message_id=user_message_id,
            assistant_message_id=assistant_id,
            session_id=session_id,
            intent_kind=parsed.kind,
            status="refused",
            echo_text=parsed.echo_text,
            clarification_question=None,
        )

    def _finish_clarification(
        self, session_id: str, user_message_id: int, parsed: ParsedIntent
    ) -> MessageResult:
        question = parsed.clarification_question or "请补充说明。"
        self._set_pending(session_id, parsed.pending)
        assistant_id = self._append_assistant(
            session_id=session_id,
            content=question,
            intent_kind=parsed.kind,
            status="clarification_needed",
            payload={"echo_text": parsed.echo_text},
        )
        return MessageResult(
            message_id=user_message_id,
            assistant_message_id=assistant_id,
            session_id=session_id,
            intent_kind=parsed.kind,
            status="clarification_needed",
            echo_text=parsed.echo_text,
            clarification_question=question,
        )

    def _finish_revision_change(
        self,
        session_id: str,
        user_message_id: int,
        current: StrategySpec,
        parsed: ParsedIntent,
        *,
        param_overrides: dict[str, float] | None = None,
        symbols: list[str] | None = None,
        timeframe: str | None = None,
    ) -> MessageResult:
        child = self._build_child_revision(
            current, param_overrides=param_overrides, symbols=symbols, timeframe=timeframe
        )
        diff = _diff_revisions(current, child)
        round_id = self._round_id(session_id)
        reservation_id = f"eval-{child.spec_hash[:16]}"
        payload = self._evaluation_payload(
            session_id=session_id,
            child=child,
            round_id=round_id,
            reservation_id=reservation_id,
        )
        try:
            self._budget.start_round(round_id)
            self._budget.start_round_clock(round_id)
            self._budget.reserve(
                round_id,
                BudgetPlan(llm_calls=0, tokens=0, backtests=1),
                reservation_id=reservation_id,
                meta={"revision_id": child.strategy_revision_id, "spec_hash": child.spec_hash},
            )
            task = self._tasks.submit(
                kind="evaluate_strategy",
                payload=payload,
                budget_reserved=BudgetBlock(
                    llm_calls_reserved=0,
                    llm_calls_used=0,
                    tokens_reserved=0,
                    tokens_used=0,
                    backtests_reserved=1,
                    backtests_used=0,
                    wall_clock_limit_s=DEFAULT_ROUND_WALL_CLOCK_S,
                ),
                idempotency_sha256=canonical_payload_sha256(payload),
            )
        except BudgetExhausted as exc:
            assistant_id = self._append_assistant(
                session_id=session_id,
                content=(
                    f"预算不足，未创建评估任务：{exc.human_message}\n"
                    f"拟议修订差异：{_render_diff(diff)}"
                ),
                intent_kind=parsed.kind,
                status="budget_exhausted",
                payload={"echo_text": parsed.echo_text, "diff": [d.model_dump() for d in diff]},
            )
            return MessageResult(
                message_id=user_message_id,
                assistant_message_id=assistant_id,
                session_id=session_id,
                intent_kind=parsed.kind,
                status="budget_exhausted",
                echo_text=parsed.echo_text,
                diff=diff,
            )

        # Only a successfully submitted evaluation advances the lineage.
        self._set_current_revision(session_id, child)
        self._set_pending(session_id, None)
        content = (
            f"已创建修订 {child.strategy_revision_id}（父修订 {current.strategy_revision_id}）。"
            f"差异：{_render_diff(diff)}。评估任务已提交（{task.task_id}，状态 {task.state}）。"
        )
        assistant_id = self._append_assistant(
            session_id=session_id,
            content=content,
            intent_kind=parsed.kind,
            status="submitted",
            payload={
                "echo_text": parsed.echo_text,
                "revision_id": child.strategy_revision_id,
                "parent_revision_id": current.strategy_revision_id,
                "diff": [d.model_dump() for d in diff],
                "task_id": task.task_id,
            },
        )
        return MessageResult(
            message_id=user_message_id,
            assistant_message_id=assistant_id,
            session_id=session_id,
            intent_kind=parsed.kind,
            status="submitted",
            echo_text=parsed.echo_text,
            revision_id=child.strategy_revision_id,
            parent_revision_id=current.strategy_revision_id,
            diff=diff,
            task_id=task.task_id,
            task_state=task.state,
        )

    def _finish_ask_verdict(
        self, session_id: str, user_message_id: int, current: StrategySpec
    ) -> MessageResult:
        verdict_bundle = self._latest_verdict_for_session(session_id, current.spec_hash)
        refs: list[str] = []
        if verdict_bundle is None:
            content = (
                f"当前修订 {current.strategy_revision_id}"
                f"（{current.symbols[0]} @{current.signal_timeframe}，"
                f"倍数 {current.params.volatility_multiplier:g}，ATR 周期 {current.params.atr_period}）"
                "还没有已完成的结论。发送「评估当前策略」开始一次评估。"
            )
        else:
            task_id, verdict, artifact_refs = verdict_bundle
            refs = _verdict_refs(verdict, artifact_refs)
            content = (
                f"当前修订 {current.strategy_revision_id} 的最新结论（任务 {task_id}）："
                f"evidence_status={verdict.get('evidence_status')}，"
                f"disposition={verdict.get('disposition')}，"
                f"reason_codes={verdict.get('reason_codes')}。"
            )
        assistant_id = self._append_assistant(
            session_id=session_id,
            content=content,
            intent_kind="ask_verdict",
            status="answered",
            payload={"verdict_refs": refs},
        )
        return MessageResult(
            message_id=user_message_id,
            assistant_message_id=assistant_id,
            session_id=session_id,
            intent_kind="ask_verdict",
            status="answered",
            echo_text="结论问答：读取当前修订与最新结论作答。",
            verdict_refs=refs,
        )

    def _finish_evidence_question(
        self, session_id: str, user_message_id: int, current: StrategySpec
    ) -> MessageResult:
        verdict_bundle = self._latest_verdict_for_session(session_id, current.spec_hash)
        refs: list[str] = []
        if verdict_bundle is None:
            content = (
                "当前修订还没有可引用的结论与证据；先运行一次评估，"
                "再问「为什么」才能引用事实（不会为问答启动新回测）。"
            )
        else:
            task_id, verdict, artifact_refs = verdict_bundle
            refs = _verdict_refs(verdict, artifact_refs)
            content = (
                f"依据（结论任务 {task_id}，evidence_status={verdict.get('evidence_status')}）："
                f"reason_codes={verdict.get('reason_codes')}；"
                f"引用事实：{', '.join(refs) if refs else '（结论未携带 artifact 引用）'}。"
            )
        assistant_id = self._append_assistant(
            session_id=session_id,
            content=content,
            intent_kind="evidence_question",
            status="answered",
            payload={"verdict_refs": refs},
        )
        return MessageResult(
            message_id=user_message_id,
            assistant_message_id=assistant_id,
            session_id=session_id,
            intent_kind="evidence_question",
            status="answered",
            echo_text="证据问答：读取当前结论的证据作答，不触发新回测。",
            verdict_refs=refs,
        )

    # ------------------------------------------------------------------ tools

    def invoke_tool(self, name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Invoke a whitelisted tool with strict server-side validation."""
        handler = self._tool_registry.get(name)
        if handler is None:
            raise ToolAccessError(
                f"unknown tool {name!r}; whitelist: {sorted(self._tool_registry)}"
            )
        if not isinstance(payload, Mapping):
            raise ToolAccessError("tool payload must be a JSON object")
        result: dict[str, Any] = handler(dict(payload))
        return result

    @staticmethod
    def _require_keys(payload: dict[str, Any], allowed: set[str], required: set[str]) -> None:
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ToolAccessError(f"unknown payload keys: {unknown}")
        missing = sorted(required - set(payload))
        if missing:
            raise ToolAccessError(f"missing payload keys: {missing}")

    def _tool_ensure_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(
            payload,
            allowed={"session_id", "symbol", "timeframe"},
            required={"session_id", "symbol"},
        )
        session_id = self._validated_session_id(payload["session_id"])
        symbol = _validated_symbol(payload["symbol"])
        timeframe = _validated_timeframe(payload.get("timeframe"))
        reservation_id = f"ensure-{symbol}-{SNAPSHOT_POLICY_ID}"
        round_id = self._round_id(session_id)
        task_payload: dict[str, Any] = {
            "kind": "ensure_data",
            "session_id": session_id,
            "symbol": symbol,
            "snapshot_policy": SNAPSHOT_POLICY_ID,
            "budget_round_id": round_id,
            "budget_reservation_id": reservation_id,
        }
        if timeframe is not None:
            task_payload["timeframe"] = timeframe
        self._budget.start_round(round_id)
        self._budget.start_round_clock(round_id)
        self._budget.reserve(
            round_id,
            BudgetPlan(llm_calls=0, tokens=0, backtests=0),
            reservation_id=reservation_id,
            meta={"symbol": symbol},
        )
        task = self._tasks.submit(
            kind="ensure_data",
            payload=task_payload,
            budget_reserved=BudgetBlock(
                llm_calls_reserved=0,
                llm_calls_used=0,
                tokens_reserved=0,
                tokens_used=0,
                backtests_reserved=0,
                backtests_used=0,
                wall_clock_limit_s=DEFAULT_ROUND_WALL_CLOCK_S,
            ),
            idempotency_sha256=canonical_payload_sha256(task_payload),
        )
        return {"task_id": task.task_id, "state": task.state, "symbol": symbol}

    def _tool_evaluate_strategy(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(payload, allowed={"session_id", "spec"}, required={"session_id", "spec"})
        session_id = self._validated_session_id(payload["session_id"])
        if not isinstance(payload["spec"], Mapping):
            raise ToolAccessError("spec must be a JSON object")
        spec = StrategySpec.model_validate(dict(payload["spec"]))  # extra="forbid"
        reservation_id = f"eval-{spec.spec_hash[:16]}"
        round_id = self._round_id(session_id)
        task_payload = self._evaluation_payload(
            session_id=session_id,
            child=spec,
            round_id=round_id,
            reservation_id=reservation_id,
        )
        self._budget.reserve(
            round_id,
            BudgetPlan(llm_calls=0, tokens=0, backtests=1),
            reservation_id=reservation_id,
            meta={"revision_id": spec.strategy_revision_id, "spec_hash": spec.spec_hash},
        )
        task = self._tasks.submit(
            kind="evaluate_strategy",
            payload=task_payload,
            budget_reserved=BudgetBlock(
                llm_calls_reserved=0,
                llm_calls_used=0,
                tokens_reserved=0,
                tokens_used=0,
                backtests_reserved=1,
                backtests_used=0,
                wall_clock_limit_s=DEFAULT_ROUND_WALL_CLOCK_S,
            ),
            idempotency_sha256=canonical_payload_sha256(task_payload),
        )
        return {
            "task_id": task.task_id,
            "state": task.state,
            "revision_id": spec.strategy_revision_id,
        }

    def _tool_compare_runs(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(
            payload, allowed={"run_id_a", "run_id_b"}, required={"run_id_a", "run_id_b"}
        )
        left = self._read_run_summary(payload["run_id_a"])
        right = self._read_run_summary(payload["run_id_b"])
        return {"a": left, "b": right}

    def _tool_read_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_keys(payload, allowed={"run_id"}, required={"run_id"})
        return self._read_run_summary(payload["run_id"])

    def _read_run_summary(self, run_id: Any) -> dict[str, Any]:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ToolAccessError("run_id must be a non-empty string")
        task = self._tasks.get(run_id)  # TaskNotFoundError propagates
        result = self._tasks.get_result(run_id)
        return {
            "task_id": task.task_id,
            "kind": task.kind,
            "state": task.state,
            "result": result,
        }

    # ------------------------------------------------------------------ internals

    def _round_id(self, session_id: str) -> str:
        return f"{_ROUND_PREFIX}-{session_id}"

    def _evaluation_payload(
        self, *, session_id: str, child: StrategySpec, round_id: str, reservation_id: str
    ) -> dict[str, Any]:
        """Deterministic evaluate_strategy payload; its canonical hash doubles
        as the idempotency key (spec content + session + snapshot policy +
        budget binding ids — never timestamps or lineage-only fields)."""
        return {
            "kind": "evaluate_strategy",
            "session_id": session_id,
            "revision_id": child.strategy_revision_id,
            "spec_hash": child.spec_hash,
            "spec_content": spec_identity_content(child),
            "snapshot_policy": SNAPSHOT_POLICY_ID,
            "budget_round_id": round_id,
            "budget_reservation_id": reservation_id,
        }

    def _build_child_revision(
        self,
        current: StrategySpec,
        *,
        param_overrides: dict[str, float] | None = None,
        symbols: list[str] | None = None,
        timeframe: str | None = None,
    ) -> StrategySpec:
        if param_overrides:
            # make_revision only accepts VariantParams names; bad names or
            # ranges raise ValueError (parser pre-validated, this is a guard).
            overrides = {
                key: int(value) if key == ATR_PARAM else float(value)
                for key, value in param_overrides.items()
            }
            return make_revision(current, overrides)
        content = spec_identity_content(current)
        if symbols is not None:
            content["symbols"] = symbols
        if timeframe is not None:
            content["signal_timeframe"] = timeframe
        child_hash = compute_spec_hash(content)
        return StrategySpec.model_validate(
            {
                **content,
                "parent_revision_id": current.strategy_revision_id,
                "spec_hash": child_hash,
                "strategy_revision_id": derive_revision_id(
                    child_hash, current.strategy_revision_id
                ),
            }
        )

    def _latest_verdict_for_session(
        self, session_id: str, spec_hash: str
    ) -> tuple[str, dict[str, Any], dict[str, str]] | None:
        """Newest succeeded evaluate_strategy result for this session+spec."""
        tasks = self._tasks.list_tasks()
        for task in reversed(tasks):
            if task.kind != "evaluate_strategy" or task.state != "succeeded":
                continue
            try:
                payload = self._tasks.get_payload(task.task_id)
            except KronosError:  # pragma: no cover - payload always exists
                continue
            if payload.get("session_id") != session_id:
                continue
            if spec_hash and payload.get("spec_hash") != spec_hash:
                continue
            result = self._tasks.get_result(task.task_id)
            if result is None or "verdict" not in result:
                continue
            artifact_refs = result.get("artifact_refs")
            refs = artifact_refs if isinstance(artifact_refs, dict) else {}
            return task.task_id, dict(result["verdict"]), {str(k): str(v) for k, v in refs.items()}
        return None

    def _validated_session_id(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ToolAccessError("session_id must be a non-empty string")
        self._get_session_row(value)  # SessionNotFoundError propagates
        return value

    def _get_session_row(self, session_id: str) -> sqlite3.Row:
        with self._lock:
            row = cast(
                "sqlite3.Row | None",
                self._conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone(),
            )
        if row is None:
            raise SessionNotFoundError(f"unknown session: {session_id}")
        return row

    def _row_to_spec(self, row: sqlite3.Row) -> StrategySpec:
        with self._lock:
            revision = self._conn.execute(
                "SELECT spec_json FROM current_revision_json WHERE session_id = ?",
                (row["session_id"],),
            ).fetchone()
        if revision is None:  # pragma: no cover - create_session always seeds one
            raise SessionNotFoundError(f"session {row['session_id']} has no current revision")
        return StrategySpec.model_validate_json(str(revision["spec_json"]))

    @staticmethod
    def _row_to_pending(row: sqlite3.Row) -> PendingAdjustment | None:
        raw = row["pending_json"]
        if not raw:
            return None
        return PendingAdjustment.model_validate_json(str(raw))

    def _set_pending(self, session_id: str, pending: PendingAdjustment | None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE sessions SET pending_json = ? WHERE session_id = ?",
                (pending.model_dump_json() if pending is not None else None, session_id),
            )

    def _set_current_revision(self, session_id: str, spec: StrategySpec) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO current_revision_json (session_id, spec_json, updated_at_ms) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET spec_json = excluded.spec_json, "
                "updated_at_ms = excluded.updated_at_ms",
                (session_id, spec.model_dump_json(), now_ms()),
            )

    def _append_message(self, *, session_id: str, role: str, content: str, created_at: int) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at_ms) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, created_at),
            )
            return _require_rowid(cursor)

    def _append_assistant(
        self,
        *,
        session_id: str,
        content: str,
        intent_kind: str,
        status: str,
        payload: dict[str, Any],
    ) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO messages (session_id, role, content, intent_kind, status, "
                "payload_json, created_at_ms) VALUES (?, 'assistant', ?, ?, ?, ?, ?)",
                (
                    session_id,
                    content,
                    intent_kind,
                    status,
                    json.dumps(payload, sort_keys=True, default=str),
                    now_ms(),
                ),
            )
            return _require_rowid(cursor)

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> MessageRecord:
        payload_raw = row["payload_json"]
        payload: dict[str, Any] = json.loads(payload_raw) if payload_raw else {}
        return MessageRecord(
            id=int(row["id"]),
            session_id=str(row["session_id"]),
            role="assistant" if row["role"] == "assistant" else "user",
            content=str(row["content"]),
            intent_kind=row["intent_kind"],
            status=row["status"],
            payload=payload,
            created_at_ms=int(row["created_at_ms"]),
        )


def _validated_symbol(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if 3 <= len(normalized) <= 20 and normalized.isalnum() and normalized.isascii():
            return normalized
    raise ToolAccessError("symbol must match ^[A-Z0-9]{3,20}$")


def _validated_timeframe(value: Any) -> str | None:
    if value is None:
        return None
    if value in ("15m", "1h"):
        return str(value)
    raise ToolAccessError("timeframe must be '15m' or '1h'")


def _diff_revisions(parent: StrategySpec, child: StrategySpec) -> list[RevisionDiffEntry]:
    diff: list[RevisionDiffEntry] = []
    for key in (MULTIPLIER_PARAM, ATR_PARAM):
        old = getattr(parent.params, key)
        new = getattr(child.params, key)
        if old != new:
            diff.append(RevisionDiffEntry(field=f"params.{key}", old=_fmt(old), new=_fmt(new)))
    if parent.symbols != child.symbols:
        diff.append(
            RevisionDiffEntry(
                field="symbols", old=",".join(parent.symbols), new=",".join(child.symbols)
            )
        )
    if parent.signal_timeframe != child.signal_timeframe:
        diff.append(
            RevisionDiffEntry(
                field="signal_timeframe",
                old=parent.signal_timeframe,
                new=child.signal_timeframe,
            )
        )
    return diff


def _render_diff(diff: list[RevisionDiffEntry]) -> str:
    if not diff:
        return "无内容差异（仅修订谱系变化）"
    return "；".join(f"{entry.field} {entry.old} → {entry.new}" for entry in diff)


def _verdict_refs(verdict: Mapping[str, Any], artifact_refs: Mapping[str, str]) -> list[str]:
    refs = [f"{key}={path}" for key, path in sorted(artifact_refs.items())]
    reason_codes = verdict.get("reason_codes")
    if isinstance(reason_codes, list):
        refs.extend(f"reason_code={code}" for code in reason_codes)
    return refs


def _fmt(value: float | int | str) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _require_rowid(cursor: sqlite3.Cursor) -> int:
    """Return the INSERT rowid; sqlite always provides one for these inserts."""
    rowid = cursor.lastrowid
    if rowid is None:  # pragma: no cover - defensive
        raise ConversationError("sqlite INSERT returned no rowid")
    return int(rowid)
