import argparse
import os
import xmlrpc.client

from flask import Flask, jsonify, render_template, request


def load_legacy_users(history_path: str) -> list[str]:
    """Load legacy usernames from the JSONL history file, if present."""
    users: set[str] = set()
    if not os.path.exists(history_path):
        return []

    try:
        import json

        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                username = str(payload.get("username") or "").strip()
                if username:
                    users.add(username)
    except OSError:
        # If we cannot read the file, fall back to an empty list.
        return []

    return sorted(users)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Flask web UI for the XML-RPC chat server."
    )
    parser.add_argument(
        "--server_host",
        default="127.0.0.1",
        help="Hostname or IP address of the XML-RPC chat server (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--server_port",
        type=int,
        default=9000,
        help="Port where the XML-RPC chat server is listening (default: 9000).",
    )
    parser.add_argument(
        "--flask_host",
        default="127.0.0.1",
        help="Host interface for the Flask app (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--flask_port",
        type=int,
        default=5000,
        help="Port for the Flask app (default: 5000).",
    )
    return parser


def create_app(proxy: xmlrpc.client.ServerProxy, legacy_users: list[str]) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return render_template("chat.html", legacy_users=legacy_users)

    @app.get("/api/messages")
    def get_messages():
        last_id_raw = request.args.get("last_id", "0")
        room = (request.args.get("room") or "public").strip().lower()

        try:
            last_id = int(last_id_raw)
        except ValueError:
            last_id = 0

        try:
            messages = proxy.get_messages(last_id, room)
            return jsonify(messages)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/messages")
    def post_message():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get("username") or "").strip()
        text = (data.get("text") or "").strip()
        room = (data.get("room") or "public").strip().lower()

        if not username or not text:
            return jsonify({"error": "username and text are required"}), 400

        if room not in {"public", "founders"}:
            return jsonify({"error": "invalid room"}), 400

        try:
            msg_id = proxy.send_message(username, text, room)
            return jsonify({"id": msg_id})
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": str(exc)}), 500

    return app


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    server_url = f"http://{args.server_host}:{args.server_port}/RPC2"
    proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True)

    history_path = os.path.join(os.path.dirname(__file__), "chat_history.jsonl")
    legacy_users = load_legacy_users(history_path)

    app = create_app(proxy, legacy_users)
    app.run(host=args.flask_host, port=args.flask_port, debug=False)


if __name__ == "__main__":
    main()

