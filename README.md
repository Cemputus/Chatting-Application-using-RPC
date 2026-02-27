# Cloud Computing Assignments – Execution Guide

This document explains how to **set up the environment** and **execute** the three Cloud Computing assignments shown in the course outline:

1. Chatting Application using RPC/RMI  
2. Web service to calculate the currency exchange rate  
3. MapReduce application for word indexing in a file  

The instructions are written from the perspective of a data scientist who is comfortable with Python, distributed systems, and command‑line workflows.

---

## 1. Prerequisites

- **Operating System**
  - Windows 10 or later (instructions use PowerShell syntax).

- **Core Software**
  - **Python**: version 3.9 or later (`python --version`).
  - **Java Development Kit (JDK)**: version 11 or later (required if you implement RMI‑based chat or Hadoop MapReduce).
  - **Git**: to clone and version‑control the repository.

- **Python Packages**
  - Will be installed from `requirements.txt` (if present) using:

    ```powershell
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

- **Optional Distributed Computing Stack**
  - **Apache Hadoop** or **Apache Spark** (local or cluster) for the MapReduce assignment.
  - For a pure‑Python local MapReduce prototype, you may also use libraries such as `mrjob` or `pyspark` without a full cluster.

---

## 2. Repository Layout (recommended)

It is recommended to organise this folder as:

- `cloud_rpc_chat/` – RPC/RMI chatting application  
- `currency_exchange_service/` – REST API or gRPC service for FX rates  
- `mapreduce_word_index/` – MapReduce / Spark job for word indexing  
- `requirements.txt` – shared Python dependencies  
- `README.md` – this file  
- `start_chat_app.bat` – helper script to launch the chat stack  

If your structure differs, conceptually map each section below to the corresponding directory in your project.

---

## 3. Common Environment Setup

From `Semester 2/Cloud_Computing`:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
```

### 3.1 Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your PowerShell prompt should show `(.venv)` indicating the environment is active.

### 3.2 Install dependencies

If `requirements.txt` exists in this directory:

```powershell
pip install -r requirements.txt
```

For data‑science‑oriented solutions, typical packages might include: `fastapi` or `flask`, `requests`, `pydantic`, `pandas`, `numpy`, `pyspark` or `mrjob`, etc.

---

## 3.1 Containerised deployment with Docker (optional but professional)

For a production‑style deployment where **anyone with a link can join the conversation**, the chat stack is containerised and uses **PostgreSQL** as a backing store for messages. The recommended setup is a two‑service composition:

- `db`: PostgreSQL instance (official `postgres:16-alpine` image).
- `app`: this repository, built from the provided `Dockerfile`, running both `server.py` and `flask_app.py`.

From this directory you can build the application image:

```powershell
docker build -t rpc-chat .
```

Or, more conveniently, start both the app and the database together using `docker-compose.yml`:

```powershell
docker compose up --build
```

This will:

- start a PostgreSQL container seeded with a `chatdb` database,
- start the chat application container configured to connect to that database,
- expose the Flask web UI on `http://localhost:5000/`.

To make it publicly reachable, run the same composition on a cloud container platform (e.g. Render, Railway, Google Cloud Run behind a managed Postgres service, or Azure Container Apps with Azure Database for PostgreSQL) and expose port `5000` behind a public URL; all users who open that URL will join the same shared conversation, backed by the Postgres‐persisted chat history.

---

## 4. Assignment 1 – RPC/RMI Chatting Application

This assignment implements a **distributed chat system** where multiple clients communicate via a central server using **RPC** (Remote Procedure Call) or **RMI** (Remote Method Invocation).

Assume the implementation lives in `cloud_rpc_chat/` and exposes:

- a **server module**: `server.py` (or `Server.java`)  
- a **client module**: `client.py` (or `Client.java`)  
- a **Flask web UI**: `flask_app.py` with template `templates/chat.html`  

### 4.0 High‑level design (implemented version)

- **RPC technology**: Python `xmlrpc.server` and `xmlrpc.client` are used to implement a lightweight RPC layer on top of HTTP.  
- **Server state**: `server.py` keeps a logical append‑only log of chat messages, each with `(id, username, text, timestamp)`, and **persists them in a PostgreSQL table** (`chat_messages`) so that history survives container restarts and can be scaled or queried independently.  
- **RPC operations**:
  - `send_message(username, text) -> id`: validates input, appends a new message, returns its unique ID.
  - `get_messages(last_id) -> List[Dict]`: returns all messages whose IDs are greater than `last_id`.  
- **Terminal client** (`client.py`): runs a background polling loop that periodically calls `get_messages`, while the foreground loop sends text typed by the user via `send_message`.  
- **Flask GUI** (`flask_app.py` + `templates/chat.html`): exposes REST‑style JSON endpoints `/api/messages` (GET/POST) which internally call the XML‑RPC server; a small JavaScript frontend polls and posts to those endpoints to render a live chat window in the browser.

### 4.1 Starting the RPC server (Python XML‑RPC example)

From the project root:

```powershell
cd cloud_rpc_chat
python server.py --host 0.0.0.0 --port 9000
```

Typical server parameters:

- `--host`: interface to bind (use `0.0.0.0` to accept remote connections, `127.0.0.1` for local only).
- `--port`: TCP port to listen on.

In this **XML‑RPC** implementation, `server.py`:

- creates a `SimpleXMLRPCServer` bound to `host:port`,
- registers remote procedures such as `send_message(username, text)` and `get_messages(last_id)`,
- maintains an in‑memory, thread‑safe message log to broadcast messages between connected clients.

Leave this process running in its own terminal.

### 4.2 Running the chat client (Python example)

Open a new PowerShell window, activate the virtual environment, then:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.venv\Scripts\Activate.ps1
cd cloud_rpc_chat

python client.py --server_host 127.0.0.1 --server_port 9000 --username Edube
```

Run another instance with a different `--username` to simulate a second user:

```powershell
python client.py --server_host 127.0.0.1 --server_port 9000 --username Nsubuga
```

Under the hood, each client:

- connects to the XML‑RPC endpoint exposed by the server,
- invokes `send_message` RPCs whenever the user types into the console,
- continually polls `get_messages` to stream new messages from other users in near real‑time.

### 4.3 Flask web GUI

Instead of the terminal client, a browser‑based GUI is available via Flask.  
The Flask app exposes two JSON endpoints that act as an HTTP façade over the XML‑RPC server:

- `GET /api/messages?last_id=<int>` → proxies to `get_messages(last_id)` and returns a JSON array of messages.  
- `POST /api/messages` with body `{"username": "...", "text": "..."}` → proxies to `send_message(username, text)` and returns the new message ID.

The HTML template `templates/chat.html` uses JavaScript to:

- lock in a username (e.g. **Edube**, **Nsubuga**),
- poll `/api/messages` every second to fetch new messages,
- send messages using `fetch("/api/messages", { method: "POST", ... })`,
- render a live chat timeline with timestamps in the browser.

To run the Flask GUI manually:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd cloud_rpc_chat
python server.py --host 0.0.0.0 --port 9000
```

In a **second** PowerShell window:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.venv\Scripts\Activate.ps1
cd cloud_rpc_chat
python flask_app.py --server_host 127.0.0.1 --server_port 9000 --flask_host 127.0.0.1 --flask_port 5000
```

Then open `http://127.0.0.1:5000/` in a browser, enter a username, and start chatting.

### 4.4 One‑click startup using `start_chat_app.bat`

For convenience, a Windows batch script orchestrates the full stack:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
start_chat_app.bat
```

The script will:

- activate `.venv` if present,
- open one terminal running `server.py` (XML‑RPC chat server with persistent history),
- open a second terminal running `flask_app.py` (Flask GUI),
- open your default browser pointing at `http://127.0.0.1:5000/`.

### 4.3 Java RMI variant (if used)

If your implementation uses Java RMI:

1. **Compile sources**:

   ```powershell
   cd cloud_rpc_chat
   javac *.java
   ```

2. **Start the RMI registry**:

   ```powershell
   start rmiregistry 1099
   ```

3. **Start the server**:

   ```powershell
   java ChatServer
   ```

4. **Run clients**:

   ```powershell
   java ChatClient Edube
   java ChatClient Nsubuga
   ```

---

## 5. Assignment 2 – Currency Exchange Rate Web Service

This assignment exposes a **web API** that returns currency exchange rates, typically consumed by other systems or dashboards.

Assume the implementation lives in `currency_exchange_service/` and is built with **FastAPI** (similar steps apply to Flask or Django).

### 5.1 Starting the web service

From the project root:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.venv\Scripts\Activate.ps1
cd currency_exchange_service

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Where:

- `app:app` refers to `app.py` containing the FastAPI instance `app`.
- `--reload` enables auto‑reloading during development.

### 5.2 Example API contract

Expose an endpoint such as:

- `GET /fx?base=USD&target=EUR&amount=100`

Expected JSON response (example):

```json
{
  "base": "USD",
  "target": "EUR",
  "amount": 100.0,
  "rate": 0.92,
  "converted_amount": 92.0,
  "timestamp_utc": "2026-02-27T10:00:00Z",
  "data_source": "ECB"
}
```

### 5.3 Calling the service from the command line

Using `curl`:

```powershell
curl "http://localhost:8000/fx?base=USD&target=EUR&amount=100"
```

Using Python (e.g. from a notebook or script):

```python
import requests

resp = requests.get(
    "http://localhost:8000/fx",
    params={"base": "USD", "target": "EUR", "amount": 100},
    timeout=5,
)
resp.raise_for_status()
data = resp.json()
print(data)
```

Behind the scenes, the service can:

- Pull live rates from an external FX API (e.g. ECB, OpenExchangeRates).
- Cache responses in memory or Redis to reduce latency and external calls.
- Log full request/response metadata for reproducibility and auditing.

---

## 6. Assignment 3 – MapReduce Word Indexing Application

This assignment builds a **MapReduce pipeline** that reads a text corpus and produces an **inverted index**: for each unique word, the list of document IDs (or line numbers) where it appears.

Assume the implementation lives in `mapreduce_word_index/`.

### 6.1 Local execution with PySpark (recommended)

From the project root:

```powershell
cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
.venv\Scripts\Activate.ps1
cd mapreduce_word_index

python job_word_index.py --input data/sample_corpus/ --output output/word_index
```

Typical arguments:

- `--input`: path to a directory containing one or more text files.
- `--output`: directory where the job writes the inverted index (often as partitioned files).

Inside `job_word_index.py`, a standard PySpark pattern would:

1. Create a `SparkSession`.
2. Read the input files as an RDD or DataFrame.
3. **Map**: tokenise lines into `(word, document_id)` key‑value pairs.
4. **Reduce / groupByKey**: aggregate document IDs per word.
5. Persist the result back to disk in a columnar or text format.

### 6.2 Hadoop Streaming / mrjob variant

If implemented using Hadoop Streaming or the `mrjob` library:

```powershell
python word_index_mrjob.py \
    --input data/sample_corpus/*.txt \
    --output-dir output/word_index \
    --no-conf
```

Where:

- `word_index_mrjob.py` defines a `MRJob` with `mapper`, `combiner`, and `reducer` methods that emit `(word, doc_id)` pairs and aggregate them.

The resulting output typically consists of lines like:

```text
analytics    ["doc1.txt", "doc3.txt"]
cloud        ["doc2.txt"]
pipeline     ["doc1.txt", "doc2.txt", "doc3.txt"]
```

---

## 7. Verification and Testing

- **Unit tests** (if present) can be run from the project root:

  ```powershell
  cd "C:\Users\CEN\OneDrive\Documents\Data_Science\year3\Semester 2\Cloud_Computing"
  .venv\Scripts\Activate.ps1
  pytest
  ```

- For each assignment, perform at least:
  - **Happy‑path tests** (expected input, normal load).
  - **Edge‑case tests** (invalid messages in chat, unsupported currency pairs, empty files in MapReduce).
  - **Performance sanity checks** (latency of RPC calls, throughput of FX API, scaling behaviour of MapReduce with larger input).

---

## 8. Reproducibility and Reporting

As a data scientist, document in your project report or notebook:

- Exact versions of Python, Java, and external libraries.
- Configuration parameters used for each run (ports, hosts, batch size, parallelism).
- Any cloud resources leveraged (e.g. GCP Dataproc, Cloud Run, Kubernetes Engine) and how the local commands map to their cloud‑native equivalents.

This README, together with clear code structure, should allow another engineer to **clone the repository, recreate the environment, and execute all three assignments end‑to‑end** with minimal friction.

