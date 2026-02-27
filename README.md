# Chatting Application using RPC/RMI

This repository contains a **chat application** that we implemented using **Remote Procedure Calls (RPC)**, backed by a **PostgreSQL** database and exposed through a modern **Flask web UI**.

The goal of this project is to demonstrate, in a realistic way, how we can:

- Use RPC (via Python XML‑RPC) to separate chat logic from clients.
- Persist chat history in a relational database instead of flat files.
- Run the whole stack in **Docker** with **docker‑compose**.
- Provide a slick browser UI with **multiple rooms** (Public vs Founders) and username locking.

Throughout this README we use “we” because this project is a joint effort.

---

## Developers

This chat application was designed and implemented by:

- **GULOBA EMMANUEL EDUBE** – [GitHub profile](https://github.com/Edube20Emmanuel)  
- **Emmanuel Nsubuga** – [GitHub profile](https://github.com/Cemputus)  

We jointly designed the architecture, wrote the code, wired up Docker/Postgres, and produced this documentation.

---

## 1. Project overview

The system implements a **distributed chat** where multiple clients talk to a central server over RPC:

- The **chat server** (`cloud_rpc_chat/server.py`) exposes RPC methods and owns all chat logic.
- A **Flask app** (`cloud_rpc_chat/flask_app.py`) presents an HTTP/JSON and HTML interface on top of the RPC server.
- A **browser SPA** (`cloud_rpc_chat/templates/chat.html`) provides a modern chat experience with:
  - Sidebar for **Public** and **Founders** chat rooms.
  - Username input and **Lock** button.
  - Scrollable message history with timestamps.
  - Realtime behaviour using polling.
- Optionally, we also provide:
  - A **terminal client** (`cloud_rpc_chat/client.py`).
  - A **Tkinter GUI client** (`cloud_rpc_chat/gui_client.py`) for desktop tests.

We support two logical chats:

- **Public room** – anyone with the URL can join.
- **Founders room** – restricted to “founder” usernames, discovered from an original `chat_history.jsonl` file.

All messages for both rooms are stored in a single `chat_messages` table in PostgreSQL.

---

## 2. Repository layout

Key files and directories:

- `cloud_rpc_chat/`
  - `server.py` – XML‑RPC chat server backed by PostgreSQL.
  - `client.py` – command‑line chat client.
  - `gui_client.py` – Tkinter desktop client.
  - `flask_app.py` – Flask web API and HTML renderer.
  - `templates/chat.html` – browser UI with sidebar rooms.
  - `chat_history.jsonl` – legacy history; used to detect “founder” usernames.
- `Dockerfile` – builds the application image (server + Flask app).
- `docker-compose.yml` – runs the app and PostgreSQL together.
- `start_chat_app.bat` – local Windows helper script.
- `requirements.txt` – Python dependencies.
- `.gitignore` – ignores `.venv/`, `__pycache__/`, and `chat_history.jsonl`.

---

## 3. Technology stack

- **Language**: Python 3.11+
- **RPC layer**: `xmlrpc.server` and `xmlrpc.client`
- **Web framework**: Flask
- **Database**: PostgreSQL 16 (accessed via `psycopg[binary]`)
- **Containerisation**: Docker, docker‑compose
- **Frontend**: HTML/CSS/JavaScript (no heavy frontend framework)

We intentionally kept the stack lean so the focus stays on the RPC model and deployment story.

---

## 4. Local development setup (without Docker)

All commands below assume we are in the project root:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
```

### 4.1 Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Your prompt should show `(.venv)` after activation.

### 4.2 Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

This installs Flask and the PostgreSQL driver (`psycopg[binary]`).

> For non‑Docker development, configure `CHAT_DB_HOST`, `CHAT_DB_PORT`, `CHAT_DB_NAME`, `CHAT_DB_USER`, and `CHAT_DB_PASSWORD` (or pass them to `server.py` via command‑line flags) to point to your Postgres instance.

### 4.3 Run the XML‑RPC server and Flask app manually

1. **Start the chat server**:

   ```powershell
   cd cloud_rpc_chat
   python server.py --host 0.0.0.0 --port 9000
   ```

   Leave this running.

2. **Start the Flask web UI** (in a second PowerShell window):

   ```powershell
   cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
   .\.venv\Scripts\Activate.ps1
   cd cloud_rpc_chat

   python flask_app.py --server_host 127.0.0.1 --server_port 9000 --flask_host 127.0.0.1 --flask_port 5000
   ```

3. **Open the UI**:

   Visit `http://127.0.0.1:5000/` in your browser, choose a username, click **Lock**, and start chatting.

### 4.4 One‑click script (`start_chat_app.bat`)

On Windows you can use the helper script:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.\start_chat_app.bat
```

It will:

- Activate `.venv` (if present).
- Start `server.py` in one window.
- Start `flask_app.py` in another.
- Open your default browser at `http://127.0.0.1:5000/`.

---

## 5. Docker + PostgreSQL deployment

For a more professional deployment, we containerise the stack and run it with `docker-compose`.

### 5.1 Build the application image

```powershell
docker build -t rpc-chat .
```

### 5.2 Start the stack with docker‑compose

```powershell
docker compose up --build
```

This will:

- Start a `db` service (`postgres:16-alpine`) with:
  - `POSTGRES_DB=chatdb`
  - `POSTGRES_USER=chatuser`
  - `POSTGRES_PASSWORD=chatpass`
- Start an `app` service built from this repo (`Dockerfile`), configured via:

  ```env
  CHAT_DB_HOST=db
  CHAT_DB_PORT=5432
  CHAT_DB_NAME=chatdb
  CHAT_DB_USER=chatuser
  CHAT_DB_PASSWORD=chatpass
  ```

- Expose the web UI at `http://localhost:5000/`.

To deploy in the cloud, run the same image on a container platform (Render/Railway/Cloud Run/Azure Container Apps) and connect it to a managed Postgres instance, exposing port `5000` to the internet.

---

## 6. Chat server design (`server.py`)

### 6.1 Data model

We store messages in a single table:

- `chat_messages`:
  - `id SERIAL PRIMARY KEY`
  - `username TEXT NOT NULL`
  - `room TEXT NOT NULL DEFAULT 'public'`
  - `text TEXT NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

We treat this as an **append‑only log** of events. Each message is associated with a `room`:

- `public` – default room for everyone with the URL.
- `founders` – reserved for “founder” usernames (derived from `chat_history.jsonl`).

### 6.2 XML‑RPC API

The server exposes two RPC methods over XML‑RPC:

- `send_message(username, text, room='public') -> id`  
  - Validates `username` and `text` (non‑empty).
  - Normalises `room` and enforces that it is either `'public'` or `'founders'`.
  - Inserts a new row into `chat_messages` and returns the new `id`.

- `get_messages(last_id, room='public') -> List[Dict]`  
  - Interprets `last_id` as an integer, defaulting to `0` if invalid.
  - Returns all messages where `id > last_id AND room = <room>`, ordered by `id`.
  - Each message is returned as:

    ```python
    {
        "id": int,
        "username": str,
        "text": str,
        "timestamp": float,  # UNIX epoch seconds
    }
    ```

### 6.3 Concurrency and schema

On startup, `server.py`:

- Ensures the `chat_messages` table exists.
- Ensures the `room` column exists and defaults to `'public'`.

Write operations are wrapped in a `threading.Lock` to keep inserts atomic and predictable from the app’s perspective.

---

## 7. Web API and browser client

### 7.1 Flask API (`flask_app.py`)

Flask acts as an HTTP façade over the XML‑RPC server:

- `GET /`  
  - Renders `templates/chat.html`.
  - Before rendering, we parse `chat_history.jsonl` (if present) to build a `LEGACY_USERS` list. These are the users allowed into the **Founders** room.

- `GET /api/messages?last_id=<int>&room=<room>`  
  - Forwards the request to `get_messages(last_id, room)` via XML‑RPC.
  - Returns a JSON array of messages.

- `POST /api/messages`  
  - Accepts JSON: `{ "username": "...", "text": "...", "room": "public|founders" }`.
  - Validates input and forwards to `send_message(username, text, room)`.
  - Returns `{ "id": <new_id> }` on success.

Flask itself remains stateless; all durable state lives in Postgres.

### 7.2 Browser UI (`templates/chat.html`)

Our front‑end is a single page with:

- A **sidebar** listing:
  - `Public chat` (always available).
  - `Founders chat` (enabled only if the locked username is in `LEGACY_USERS`).
- A **header** with:
  - Username field.
  - **Lock** button to confirm identity.
- A **messages** area:
  - Scrollable, shows `[HH:MM:SS] username: text`.
  - Highlights your own messages.
- A **footer** where users type messages and click **Send** (or press Enter).

Behaviour:

- When you click **Lock**:
  - Your username is stored in `localStorage` under `rpcChatUsername`.
  - We check if your name is in `LEGACY_USERS`:
    - If yes → Founders button becomes enabled.
    - If no → Founders stays disabled, and clicking it shows an explanatory status message.
  - The username field and Lock button are disabled to mimic a login.

- When you switch rooms:
  - `currentRoom` becomes either `public` or `founders`.
  - We clear the timeline, reset `lastId` to `0`, and fetch history for that room.

- Realtime updates:
  - Every second we call `GET /api/messages?last_id=<lastId>&room=<currentRoom>`.
  - We append any new messages and move `lastId` forward.
  - When we send a message, we optimistically append it locally and set `lastId` to the returned `id` so we don’t render it twice when the polling loop sees it again.

This approach provides a “professional” user experience without the complexity of WebSockets.

---

## 8. Additional clients

Besides the browser, we implemented:

- **Terminal client (`client.py`)**  
  Useful for quick smoke tests of the RPC API. It:
  - Connects to the XML‑RPC endpoint.
  - Starts a background thread to call `get_messages(last_id)` in a loop.
  - Reads from stdin and calls `send_message(...)` when you type.

- **Tkinter GUI client (`gui_client.py`)**  
  A small desktop client that uses the same RPC API but draws a native window using Tkinter. It has:
  - Scrolling text area for messages.
  - Input box and **Send** button.
  - A periodic polling loop to keep messages up‑to‑date.

Both are optional, but they helped us validate the backend from multiple angles.

---

## 9. Testing and validation

When we test this project, we focus on:

- **Happy‑path**:
  - Two or more browser sessions chatting in the Public room.
  - Two founders chatting in the Founders room with messages not leaking to Public.

- **Persistence**:
  - Send messages, stop Docker or local processes, restart, and verify history is still present for both rooms.

- **Edge cases**:
  - Empty username or message (server rejects).
  - Invalid room values (server and Flask reject).
  - Database or server downtime: clients surface readable status messages instead of crashing.

Because the XML‑RPC surface is so small (two main methods), it is easy to unit‑test and reason about.

---

## 10. What this project demonstrates

With this Chatting Application using RPC/RMI we show:

- How to design a small but realistic **RPC‑based chat backend**.
- How to integrate **PostgreSQL** for durable, queryable message storage.
- How to containerise a Python microservice with **Docker** and **docker‑compose**.
- How to build a simple but modern **web chat UI** with multi‑room support and a persistent identity model.

Another engineer can clone this repository, run a couple of commands, and get a fully working, Postgres‑backed chat system that they can extend, analyse, or redeploy in their own environment.

