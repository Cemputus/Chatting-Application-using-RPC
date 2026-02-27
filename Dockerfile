FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy chat application code
COPY cloud_rpc_chat ./cloud_rpc_chat

# Port exposed by the Flask web UI
EXPOSE 5000

# Start XML-RPC chat server and Flask web UI in a single container.
# Database connectivity is configured via environment variables:
#   CHAT_DB_HOST, CHAT_DB_PORT, CHAT_DB_NAME, CHAT_DB_USER, CHAT_DB_PASSWORD
CMD ["sh", "-c", "\
python cloud_rpc_chat/server.py --host 0.0.0.0 --port 9000 & \
python cloud_rpc_chat/flask_app.py --server_host 127.0.0.1 --server_port 9000 --flask_host 0.0.0.0 --flask_port 5000 \
"]

