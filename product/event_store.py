"""
Lightweight Local Event Store and Session Manager for Encrypted Traffic Monitor.

Stores prediction and telemetry metadata strictly without application payloads or raw packets.
Provides atomic SQLite persistence, indexed querying, session management, and CSV export.

Required Searchable Fields:
- timestamp
- flow_id
- prediction (predicted_class)
- confidence
- prediction_state
- packets_observed
- latency (latency_us)
- model_id
"""

from contextlib import contextmanager
import csv
import logging
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class LocalEventStore:
    """
    Lightweight, thread-safe local event store for live prediction metadata.
    """

    def __init__(self, db_path: str | Path = "data/events/event_store.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.active_session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self.events_stored_count: int = 0
        self._init_db()

    def get_active_session_id(self) -> Optional[str]:
        """Returns the currently active session ID from memory or SQLite."""
        if self.active_session_id:
            return self.active_session_id
        try:
            with self._lock, self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT session_id FROM monitoring_sessions WHERE status = 'ACTIVE' ORDER BY start_time DESC LIMIT 1"
                )
                row = cur.fetchone()
                if row:
                    self.active_session_id = row["session_id"]
                    return self.active_session_id
        except Exception as e:
            logger.debug("Failed to query active session from SQLite: %s", e)
        return None

    def set_active_session_id(self, session_id: str) -> None:
        """Sets the active session ID explicitly in memory."""
        self.active_session_id = session_id

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prediction_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp REAL NOT NULL,
                    flow_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    feature_profile TEXT NOT NULL,
                    prediction TEXT,
                    predicted_class TEXT,
                    predicted_family TEXT,
                    confidence REAL,
                    family_confidence REAL,
                    fine_confidence REAL,
                    composed_confidence REAL,
                    prediction_state TEXT NOT NULL,
                    packets_observed INTEGER NOT NULL,
                    elapsed_seconds REAL NOT NULL,
                    latency_us REAL NOT NULL,
                    operating_mode TEXT NOT NULL,
                    evidence_class TEXT,
                    protocol TEXT,
                    session_id_hash TEXT,
                    fine_classification_reason TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON prediction_events (timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_flow_id ON prediction_events (flow_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_state ON prediction_events (prediction_state);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON prediction_events (session_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_mode ON prediction_events (operating_mode);")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_sessions (
                    session_id TEXT PRIMARY KEY,
                    session_name TEXT,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    status TEXT NOT NULL,
                    operating_mode TEXT NOT NULL,
                    total_events INTEGER DEFAULT 0
                );
            """)

            # Automatic schema migration for existing databases
            for col_name, col_type in [
                ("predicted_class", "TEXT"),
                ("evidence_class", "TEXT"),
                ("family_confidence", "REAL"),
                ("fine_confidence", "REAL"),
                ("composed_confidence", "REAL"),
                ("fine_classification_reason", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE prediction_events ADD COLUMN {col_name} {col_type};")
                except Exception:
                    pass

            # Backfill predicted_class from prediction column if missing
            try:
                conn.execute("UPDATE prediction_events SET predicted_class = prediction WHERE (predicted_class IS NULL OR predicted_class = '') AND prediction IS NOT NULL AND prediction != '';")
            except Exception:
                pass
            conn.commit()

    def start_session(
        self,
        session_name: Optional[str] = None,
        operating_mode: str = "LIVE_NPCAP",
    ) -> str:
        """Starts a new named monitoring session."""
        now = time.time()
        sess_id = f"SESS-{int(now)}-{time.perf_counter_ns() % 10000:04d}"
        name = session_name or f"Session_{time.strftime('%Y%m%d_%H%M%S', time.localtime(now))}"

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO monitoring_sessions (session_id, session_name, start_time, status, operating_mode, total_events)
                VALUES (?, ?, ?, 'ACTIVE', ?, 0)
                """,
                (sess_id, name, now, operating_mode),
            )
            conn.commit()

        self.active_session_id = sess_id
        self.session_start_time = now
        logger.info("Started monitoring session [%s] (%s, mode=%s)", sess_id, name, operating_mode)
        return sess_id

    def stop_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Stops an active monitoring session and returns a summary."""
        target_id = session_id or self.active_session_id
        if not target_id:
            return {"error": "No active session to stop"}

        now = time.time()
        with self._lock, self._get_connection() as conn:
            # Query session events summary
            cur = conn.execute(
                """
                SELECT COUNT(*) as event_count,
                       COUNT(DISTINCT flow_id) as flow_count,
                       AVG(confidence) as avg_confidence,
                       AVG(latency_us) as avg_latency_us,
                       SUM(CASE WHEN prediction_state = 'KNOWN_CLASS' THEN 1 ELSE 0 END) as known_count,
                       SUM(CASE WHEN prediction_state = 'LOW_CONFIDENCE' THEN 1 ELSE 0 END) as low_conf_count,
                       SUM(CASE WHEN prediction_state = 'UNKNOWN' THEN 1 ELSE 0 END) as unknown_count,
                       SUM(CASE WHEN prediction_state = 'INSUFFICIENT_EVIDENCE' THEN 1 ELSE 0 END) as insuf_count
                FROM prediction_events
                WHERE session_id = ?
                """,
                (target_id,),
            )
            row = cur.fetchone()

            # Update session status
            conn.execute(
                """
                UPDATE monitoring_sessions
                SET end_time = ?, status = 'COMPLETED', total_events = ?
                WHERE session_id = ?
                """,
                (now, row["event_count"] if row else 0, target_id),
            )
            conn.commit()

        if target_id == self.active_session_id:
            dur = max(0.0, now - (self.session_start_time or now))
            self.active_session_id = None
            self.session_start_time = None
        else:
            dur = 0.0

        summary = {
            "session_id": target_id,
            "status": "COMPLETED",
            "duration_seconds": round(dur, 2),
            "events_recorded": row["event_count"] if row else 0,
            "unique_flows": row["flow_count"] if row else 0,
            "known_predictions": row["known_count"] if row else 0,
            "low_confidence_predictions": row["low_conf_count"] if row else 0,
            "unknown_predictions": row["unknown_count"] if row else 0,
            "insufficient_evidence": row["insuf_count"] if row else 0,
            "avg_confidence": round(row["avg_confidence"] or 0.0, 4) if row else 0.0,
            "avg_latency_us": round(row["avg_latency_us"] or 0.0, 2) if row else 0.0,
        }
        logger.info("Stopped monitoring session [%s]: %s", target_id, summary)
        return summary

    def clear_session(self, session_id: Optional[str] = None) -> int:
        """Deletes events for a specific session, or all events if session_id is None."""
        with self._lock, self._get_connection() as conn:
            if session_id:
                cur = conn.execute("DELETE FROM prediction_events WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM monitoring_sessions WHERE session_id = ?", (session_id,))
            else:
                cur = conn.execute("DELETE FROM prediction_events")
                conn.execute("DELETE FROM monitoring_sessions")
            deleted = cur.rowcount
            conn.commit()

        logger.info("Cleared %d events from event store (session=%s)", deleted, session_id or "ALL")
        return deleted

    def record_event(self, event_dict: Dict[str, Any]) -> None:
        """
        Inserts a single prediction event metadata record.
        Strictly records metadata only — no raw packets.
        """
        from realtime.events import EVIDENCE_CLASS_MAP
        if hasattr(event_dict, "to_dict"):
            event_dict = event_dict.to_dict()

        sess_id = event_dict.get("session_id") or self.get_active_session_id()
        if not sess_id:
            sess_id = f"SESS-{int(time.time())}"

        raw_eid = event_dict.get("event_id")
        if not raw_eid or raw_eid == "EVT-000000":
            event_id = f"EVT-{int(time.time()*1000)}-{time.perf_counter_ns()%10000:04d}"
        else:
            event_id = raw_eid
        op_mode = str(event_dict.get("operating_mode") or "LIVE_NPCAP").upper()
        ev_class = event_dict.get("evidence_class") or EVIDENCE_CLASS_MAP.get(op_mode, "UNKNOWN_EVIDENCE")

        pred_val = event_dict.get("predicted_class") or event_dict.get("prediction")
        fam_val = event_dict.get("predicted_family")
        comp_conf = float(event_dict.get("composed_confidence") or event_dict.get("confidence") or 0.0)
        fam_conf = event_dict.get("family_confidence")
        fine_conf = event_dict.get("fine_confidence")
        fine_reason = event_dict.get("fine_classification_reason")

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO prediction_events (
                    event_id, session_id, timestamp, flow_id, model_id, feature_profile,
                    prediction, predicted_class, predicted_family, confidence,
                    family_confidence, fine_confidence, composed_confidence,
                    prediction_state, packets_observed, elapsed_seconds, latency_us,
                    operating_mode, evidence_class, protocol, session_id_hash, fine_classification_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    sess_id,
                    float(event_dict.get("timestamp", time.time())),
                    str(event_dict.get("flow_id", "UNKNOWN")),
                    str(event_dict.get("model_id", "model_lightgbm_v1")),
                    str(event_dict.get("feature_profile", "lightweight_10")),
                    pred_val,
                    pred_val,
                    fam_val,
                    comp_conf,
                    fam_conf,
                    fine_conf,
                    comp_conf,
                    str(event_dict.get("prediction_state", "KNOWN_CLASS")),
                    int(event_dict.get("packets_observed", 0)),
                    float(event_dict.get("elapsed_seconds", 0.0)),
                    float(event_dict.get("latency_us", 0.0)),
                    op_mode,
                    ev_class,
                    event_dict.get("protocol"),
                    event_dict.get("session_id_hash"),
                    fine_reason,
                ),
            )
            conn.commit()
        self.events_stored_count += 1

    def query_events(
        self,
        operating_mode: Optional[str] = None,
        prediction_state: Optional[str] = None,
        flow_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Queries stored prediction events with searchable filters."""
        query = "SELECT * FROM prediction_events WHERE 1=1"
        params: List[Any] = []

        if operating_mode:
            op_norm = operating_mode.upper()
            if op_norm in ("LIVE_NPCAP", "LIVE_MODE"):
                query += " AND operating_mode IN ('LIVE_NPCAP', 'LIVE_MODE')"
            else:
                query += " AND operating_mode = ?"
                params.append(op_norm)
        if prediction_state:
            query += " AND prediction_state = ?"
            params.append(prediction_state)
        if flow_id:
            query += " AND flow_id = ?"
            params.append(flow_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(query, params)
            rows = [dict(r) for r in cur.fetchall()]

        # Guarantee both predicted_class and prediction keys are present and synchronized
        for r in rows:
            if not r.get("predicted_class") and r.get("prediction"):
                r["predicted_class"] = r["prediction"]
            if not r.get("prediction") and r.get("predicted_class"):
                r["prediction"] = r["predicted_class"]
            if r.get("composed_confidence") is None and r.get("confidence") is not None:
                r["composed_confidence"] = r["confidence"]

        return rows

    def export_csv(
        self,
        target_path: str | Path,
        session_id: Optional[str] = None,
        operating_mode: Optional[str] = None,
    ) -> Path:
        """Exports stored event metadata to a clean CSV file."""
        out_path = Path(target_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        events = self.query_events(
            session_id=session_id,
            operating_mode=operating_mode,
            limit=100000,
        )

        fieldnames = [
            "timestamp", "flow_id", "session_id", "model_id", "feature_profile",
            "prediction", "predicted_class", "predicted_family", "confidence",
            "composed_confidence", "prediction_state", "packets_observed",
            "elapsed_seconds", "latency_us", "operating_mode", "protocol"
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for ev in events:
                writer.writerow(ev)

        logger.info("Exported %d events to CSV at %s", len(events), out_path)
        return out_path


# Global singleton instance
local_event_store = LocalEventStore()
