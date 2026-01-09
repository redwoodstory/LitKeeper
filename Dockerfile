# Build stage
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir wheel && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.13-slim

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libfreetype6 \
    libharfbuzz0b \
    libfribidi0 \
    libpng16-16 \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r -g 1000 litkeeper && \
    useradd -r -u 1000 -g litkeeper -m -s /bin/bash litkeeper

# Set up application directory
WORKDIR /litkeeper

# Copy files with correct ownership
COPY --chown=litkeeper:litkeeper app app/
COPY --chown=litkeeper:litkeeper migrations migrations/
COPY --chown=litkeeper:litkeeper run.py gunicorn.docker.conf.py startup.sh .

# Create directories with secure permissions (750 = owner rwx, group rx, no world access)
RUN mkdir -p app/data app/stories/epubs app/stories/html app/stories/covers && \
    chown -R litkeeper:litkeeper app/data app/stories && \
    chmod -R 750 app/data app/stories && \
    chmod +x startup.sh

# Set environment variables
ENV PYTHONPATH=/litkeeper
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER litkeeper

# Expose port
EXPOSE 5000

# Run the application with Gunicorn via startup script
ENTRYPOINT ["/litkeeper/startup.sh"]
CMD ["gunicorn", "-c", "gunicorn.docker.conf.py", "app:create_app()"]