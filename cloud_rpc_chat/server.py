import argparse
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List

from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

import psycopg


@dataclass
class Message:
    """In-memory representation of a chat message."""

    id: int
    username: str
    text: str
    timestamp: float


class ChatState:
    """Thread-safe store for chat messages backed by PostgreSQL."""

    def __init__(self, conn_params: Dict[str, object]) -> None:
        self._conn_params = conn_params
        self._lock = threading.Lock()
        self._ensure_schema()

    def _get_connection(self):
        return psycopg.connect(**self._conn_params)

    def _ensure_schema(self) -> None:
        """Create the messages table if it does not yet exist, and ensure the room column."""
        try:
            with self._get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        username TEXT NOT NULL,
                        room TEXT NOT NULL DEFAULT 'public',
                        text TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                # For existing deployments without the room column, add it.
                cur.execute(
                    """
                    ALTER TABLE chat_messages
                    ADD COLUMN IF NOT EXISTS room TEXT NOT NULL DEFAULT 'public';
                    """
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            logging.error("Failed to ensure chat_messages schema: %s", exc)
            raise

    def send_message(self, username: str, text: str, room: str = "public") -> int:
        """Append a new message to the log and return its ID."""
        username = (username or "").strip()
        text = (text or "").strip()

        if not username:
            raise ValueError("username must be a non-empty string")
        if not text:
            raise ValueError("text must be a non-empty string")

        room = (room or "public").strip().lower()
        if room not in {"public", "founders"}:
            raise ValueError("room must be either 'public' or 'founders'")

        with self._lock:
            try:
                with self._get_connection() as conn, conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO chat_messages (username, room, text)
                        VALUES (%s, %s, %s)
                        RETURNING id, EXTRACT(EPOCH FROM created_at);
                        """,
                        (username, room, text),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    msg_id, ts = int(row[0]), float(row[1])
                    conn.commit()
                    logging.debug(
                        "Stored message id=%s username=%s text=%s", msg_id, username, text
                    )
                    return msg_id
            except Exception as exc:  # noqa: BLE001
                logging.error("Failed to send message: %s", exc)
                raise

    def get_messages_since(self, last_id: int, room: str = "public") -> List[Dict]:
        """Return all messages with ID greater than last_id as plain dicts."""
        try:
            last_id_int = int(last_id)
        except (TypeError, ValueError):
            last_id_int = 0

        room = (room or "public").strip().lower()
        if room not in {"public", "founders"}:
            raise ValueError("room must be either 'public' or 'founders'")

        try:
            with self._get_connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id,
                           username,
                           text,
                           EXTRACT(EPOCH FROM created_at) AS ts
                    FROM chat_messages
                    WHERE id > %s AND room = %s
                    ORDER BY id ASC;
                    """,
                    (last_id_int, room),
                )
                rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            logging.error("Failed to fetch messages: %s", exc)
            raise

        return [
            {
                "id": int(row[0]),
                "username": str(row[1]),
                "text": str(row[2]),
                "timestamp": float(row[3]),
            }
            for row in rows
        ]


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="XML-RPC based chat server for the Cloud Computing assignment."
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface to bind the RPC server to (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="Port to listen on for RPC connections (default: 9000).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO).",
    )
    parser.add_argument(
        "--db-host",
        default=os.getenv("CHAT_DB_HOST", "localhost"),
        help="PostgreSQL host (default: value from CHAT_DB_HOST or 'localhost').",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("CHAT_DB_PORT", "5432")),
        help="PostgreSQL port (default: value from CHAT_DB_PORT or 5432).",
    )
    parser.add_argument(
        "--db-name",
        default=os.getenv("CHAT_DB_NAME", "chatdb"),
        help="PostgreSQL database name (default: value from CHAT_DB_NAME or 'chatdb').",
    )
    parser.add_argument(
        "--db-user",
        default=os.getenv("CHAT_DB_USER", "chatuser"),
        help="PostgreSQL user (default: value from CHAT_DB_USER or 'chatuser').",
    )
    parser.add_argument(
        "--db-password",
        default=os.getenv("CHAT_DB_PASSWORD", "chatpass"),
        help="PostgreSQL password (default: value from CHAT_DB_PASSWORD or 'chatpass').",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    conn_params = {
        "host": args.db_host,
        "port": args.db_port,
        "dbname": args.db_name,
        "user": args.db_user,
        "password": args.db_password,
    }
    logging.info(
        "Connecting to PostgreSQL at %s:%s db=%s user=%s",
        conn_params["host"],
        conn_params["port"],
        conn_params["dbname"],
        conn_params["user"],
    )
    chat_state = ChatState(conn_params)

    with SimpleXMLRPCServer(
        (args.host, args.port),
        requestHandler=RequestHandler,
        allow_none=True,
        logRequests=(args.log_level == "DEBUG"),
    ) as server:
        server.register_introspection_functions()

        server.register_function(chat_state.send_message, "send_message")
        server.register_function(chat_state.get_messages_since, "get_messages")

        logging.info("Chat RPC server listening on %s:%s", args.host, args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Shutting down chat server.")


if __name__ == "__main__":
    main()


