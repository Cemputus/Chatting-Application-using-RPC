import argparse
import threading
import time
from datetime import datetime

import xmlrpc.client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="XML-RPC chat client for the Cloud Computing assignment."
    )
    parser.add_argument(
        "--server_host",
        default="127.0.0.1",
        help="Hostname or IP address of the chat server (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--server_port",
        type=int,
        default=9000,
        help="Port where the chat server is listening (default: 9000).",
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Logical username to use in the chat.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for new messages (default: 1.0).",
    )
    return parser


def format_timestamp(epoch_seconds: float) -> str:
    dt = datetime.fromtimestamp(epoch_seconds)
    return dt.strftime("%H:%M:%S")


def message_listener(proxy: xmlrpc.client.ServerProxy, username: str, poll_interval: float) -> None:
    """Background thread that polls the server for new messages."""
    last_id = 0
    while True:
        try:
            messages = proxy.get_messages(last_id)
            for msg in messages:
                msg_id = int(msg["id"])
                author = msg["username"]
                text = msg["text"]
                ts = format_timestamp(float(msg["timestamp"]))

                if author == username:
                    # Skip echo of our own messages (already printed locally).
                    last_id = max(last_id, msg_id)
                    continue

                print(f"[{ts}] {author}: {text}")
                last_id = max(last_id, msg_id)
        except Exception as exc:  # noqa: BLE001
            # Keep the client alive even if the server is temporarily unreachable.
            print(f"[warning] Error while receiving messages: {exc}")

        time.sleep(poll_interval)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    server_url = f"http://{args.server_host}:{args.server_port}/RPC2"
    proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True)

    print(f"Connected to chat server at {server_url} as '{args.username}'.")
    print("Type your message and press Enter to send. Use /quit or Ctrl+C to exit.")

    listener_thread = threading.Thread(
        target=message_listener,
        args=(proxy, args.username, args.poll_interval),
        daemon=True,
    )
    listener_thread.start()

    try:
        while True:
            try:
                text = input("> ").strip()
            except EOFError:
                # End-of-file (e.g. Ctrl+Z on Windows).
                break

            if not text:
                continue

            if text.lower() in {"/quit", "/exit"}:
                break

            try:
                msg_id = proxy.send_message(args.username, text)
                # Locally echo the message with a synthetic timestamp for responsiveness.
                ts = format_timestamp(time.time())
                print(f"[{ts}] you ({args.username}) [{msg_id}]: {text}")
            except Exception as exc:  # noqa: BLE001
                print(f"[error] Failed to send message: {exc}")
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C.
        pass

    print("Exiting chat client.")


if __name__ == "__main__":
    main()

