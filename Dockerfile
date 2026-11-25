# Render web service: Node (re-check) + Python (server). Needs secret env NTFY_POST_URL.
FROM node:20-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY index.html package.json counter.js challenge.js verify_run.js server.py ./
CMD ["python3", "server.py"]
