import argparse
import time
from datetime import datetime
from typing import Optional

import tkinter as tk
from tkinter import scrolledtext

import xmlrpc.client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tkinter GUI chat client using XML-RPC."
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


class ChatGUI:
    def __init__(
        self,
        proxy: xmlrpc.client.ServerProxy,
        username: str,
        poll_interval: float = 1.0,
    ) -> None:
        self.proxy = proxy
        self.username = username
        self.poll_interval_ms = int(max(poll_interval, 0.2) * 1000)
        self.last_id: int = 0

        self.root = tk.Tk()
        self.root.title(f"RPC Chat – {self.username}")

        self.messages = scrolledtext.ScrolledText(self.root, state="disabled", height=20)
        self.messages.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        entry_frame = tk.Frame(self.root)
        entry_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.entry = tk.Entry(entry_frame)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._on_enter_pressed)

        send_button = tk.Button(entry_frame, text="Send", command=self.send_message)
        send_button.pack(side="left", padx=(4, 0))

        self.status_var = tk.StringVar(value="Connected")
        status_label = tk.Label(self.root, textvariable=self.status_var, anchor="w")
        status_label.pack(fill="x", padx=8, pady=(0, 4))

        # Kick off periodic polling for new messages.
        self.root.after(self.poll_interval_ms, self.poll_messages)

    def append_message(self, text: str) -> None:
        self.messages.configure(state="normal")
        self.messages.insert("end", text + "\n")
        self.messages.see("end")
        self.messages.configure(state="disabled")

    def send_message(self, event: Optional[tk.Event] = None) -> None:  # type: ignore[override]
        text = self.entry.get().strip()
        if not text:
            return

        if text.lower() in {"/quit", "/exit"}:
            self.root.quit()
            return

        try:
            msg_id = self.proxy.send_message(self.username, text)
            ts = format_timestamp(time.time())
            self.append_message(f"[{ts}] you ({self.username}) [{msg_id}]: {text}")
            self.entry.delete(0, "end")
            self.status_var.set("Connected")
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Error sending message: {exc}")

    def _on_enter_pressed(self, event: tk.Event) -> None:
        self.send_message()

    def poll_messages(self) -> None:
        try:
            messages = self.proxy.get_messages(self.last_id)
            for msg in messages:
                msg_id = int(msg["id"])
                author = msg["username"]
                text = msg["text"]
                ts = format_timestamp(float(msg["timestamp"]))

                if author != self.username:
                    self.append_message(f"[{ts}] {author}: {text}")

                if msg_id > self.last_id:
                    self.last_id = msg_id

            self.status_var.set("Connected")
        except Exception as exc:  # noqa: BLE001
            self.status_var.set(f"Receive error: {exc}")

        # Schedule next poll.
        self.root.after(self.poll_interval_ms, self.poll_messages)

    def run(self) -> None:
        welcome = (
            f"Connected as '{self.username}'. "
            "Type a message in the box below and press Enter or click Send. "
            "Use /quit or /exit to close."
        )
        self.append_message(welcome)
        self.root.mainloop()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    server_url = f"http://{args.server_host}:{args.server_port}/RPC2"
    proxy = xmlrpc.client.ServerProxy(server_url, allow_none=True)

    app = ChatGUI(proxy=proxy, username=args.username, poll_interval=args.poll_interval)
    app.run()


if __name__ == "__main__":
    main()

