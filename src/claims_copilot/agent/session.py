"""Ask-session memory: in process only, bounded, expiring (DECISIONS.md, 2026-11-15).

A session keeps the last few turns (question, status, validated statement text, claim in scope)
so a follow-up such as "what about the unit limit on that claim?" can be resolved. Nothing here
is written to disk or to the audit log. Prior turns reach the model only as a delimited block of
untrusted context; they are never instructions and never a source of citations (the evidence
registry is new for every turn).

Two identifiers per session: `token`, the random value the browser sends back (a bearer secret,
never logged), and `run_label`, a separate random label used as the ledger `eval_run_id` so the
session's spend can be summed without the token ever reaching the committed ledger.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field

MAX_TURNS = 8
MAX_SESSION_CHARS = 12_000
MAX_SESSIONS = 200
TTL_SECONDS = 30 * 60
MAX_PRIOR_STATEMENTS = 6
MAX_PRIOR_STATEMENT_CHARS = 300
GATE_TURNS = 2
BLOCKED_STATUS = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class PriorTurn:
    question: str
    status: str
    statements: tuple[str, ...]
    claim_id: str | None

    def size(self) -> int:
        return len(self.question) + sum(len(s) for s in self.statements) + 64


@dataclass
class Session:
    token: str
    run_label: str
    created: float
    last_used: float
    claim_id: str | None = None
    turns: deque[PriorTurn] = field(default_factory=lambda: deque(maxlen=MAX_TURNS))
    busy: bool = False

    @property
    def previous_question(self) -> str | None:
        """The last question that was not refused (refused text is never carried forward)."""
        kept = self._unblocked()
        return kept[-1] if kept else None

    @property
    def gate_context(self) -> str | None:
        """The last two unrefused questions joined, for the scope gate's split-ask check."""
        kept = self._unblocked()[-GATE_TURNS:]
        return " ".join(kept) if kept else None

    def _unblocked(self) -> list[str]:
        return [t.question for t in self.turns if t.status != BLOCKED_STATUS]

    def remember(self, turn: PriorTurn) -> None:
        self.turns.append(turn)
        while len(self.turns) > 1 and sum(t.size() for t in self.turns) > MAX_SESSION_CHARS:
            self.turns.popleft()

    def prior_context(self) -> str | None:
        """Earlier turns as plain lines for the model's untrusted-context block."""
        if not self.turns:
            return None
        lines: list[str] = []
        for n, t in enumerate(self.turns, start=1):
            if t.status == BLOCKED_STATUS:
                lines.append(f"Turn {n}: [blocked request, not repeated here]")
                continue
            lines.append(f"Turn {n} question: {t.question}")
            lines.append(f"Turn {n} claim in scope: {t.claim_id or 'none'}")
            lines.append(f"Turn {n} status: {t.status}")
            for s in t.statements[:MAX_PRIOR_STATEMENTS]:
                lines.append(f"Turn {n} statement (not citable): {s[:MAX_PRIOR_STATEMENT_CHARS]}")
        return "\n".join(lines)


class SessionStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = TTL_SECONDS,
        max_sessions: int = MAX_SESSIONS,
        clock: Callable[[], float] = time.monotonic,
        label_prefix: str = "ask-",
    ) -> None:
        self._label_prefix = label_prefix
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, Session] = OrderedDict()

    def __len__(self) -> int:
        with self._lock:
            self._purge()
            return len(self._sessions)

    def get_or_create(self, token: str | None) -> tuple[Session, bool]:
        """The live session for `token`, or a new one. The flag is True when a new one was made
        because the token was unknown or expired (the caller tells the investigator)."""
        with self._lock:
            self._purge()
            now = self._clock()
            session = self._sessions.get(token) if token else None
            if session is not None:
                session.last_used = now
                self._sessions.move_to_end(session.token)
                return session, False
            session = Session(
                token=secrets.token_urlsafe(24),
                run_label=self._label_prefix + secrets.token_hex(6),
                created=now,
                last_used=now,
            )
            self._sessions[session.token] = session
            idle = (t for t, s in list(self._sessions.items()) if not s.busy and s is not session)
            while len(self._sessions) > self._max:
                oldest = next(idle, None)
                if oldest is None:
                    break
                del self._sessions[oldest]
            return session, token is not None

    def clear(self, token: str | None) -> bool:
        """Drop a session. A busy one is left alone: its turn is still mutating it, the browser
        discards that turn's late response, and the session expires by TTL once idle."""
        with self._lock:
            if not token:
                return False
            session = self._sessions.get(token)
            if session is None or session.busy:
                return False
            del self._sessions[token]
            return True

    def try_begin(self, session: Session) -> bool:
        """Mark a session busy; False if a question is already running in it."""
        with self._lock:
            if session.busy:
                return False
            session.busy = True
            return True

    def end(self, session: Session) -> None:
        with self._lock:
            session.busy = False
            session.last_used = self._clock()

    def _purge(self) -> None:
        cutoff = self._clock() - self._ttl
        for token in [t for t, s in self._sessions.items() if s.last_used < cutoff and not s.busy]:
            del self._sessions[token]
