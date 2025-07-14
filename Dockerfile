FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY . .
RUN pip install --no-cache-dir .

# Set environment variables
ENV ZETTELKASTEN_NOTES_DIR=/data/notes
ENV ZETTELKASTEN_DATABASE_PATH=/data/db/zettelkasten.db
ENV ZETTELKASTEN_LOG_LEVEL=DEBUG
ENV ZETTELKASTEN_FASTMCP_TRANSPORT=streamable-http

# Create necessary directories
RUN mkdir -p /data/notes /data/db

ENV FASTMCP_HOST 0.0.0.0
ENV FASTMCP_PORT=8000
EXPOSE 8000

# Set the entry point
ENTRYPOINT ["zettelkasten-mcp"]
