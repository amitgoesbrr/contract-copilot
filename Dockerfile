# ============================================================================
# AI Contract Reviewer & Negotiation Copilot - Docker Image
# ============================================================================
#
# Multi-stage build for optimized production image
# Python 3.11 slim base for minimal size
#
# Build: docker build -t contract-copilot:latest .
# Run: docker run -p 8000:8000 -e GOOGLE_API_KEY=your_key contract-copilot:latest
# ============================================================================

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser adk/ ./adk/
COPY --chown=appuser:appuser api/ ./api/
COPY --chown=appuser:appuser memory/ ./memory/
COPY --chown=appuser:appuser tools/ ./tools/
COPY --chown=appuser:appuser evaluation/ ./evaluation/
COPY --chown=appuser:appuser run_api.py .


# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_DIR=/app/logs \
    DATABASE_URL=sqlite:///./data/contract_copilot.db \
    API_HOST=0.0.0.0 \
    API_PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "run_api.py"]
