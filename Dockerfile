FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by some pip packages (openpyxl, kaleido)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer-cached)
COPY environment.yml ./
RUN pip install --no-cache-dir \
        "numpy>=1.26" \
        "pandas>=2.2" \
        "openpyxl>=3.1" \
        "dash>=2.17" \
        "dash-bootstrap-components>=1.6" \
        "plotly>=5.22" \
        "kaleido>=0.2.1"

# Copy source and sample data
COPY src/ ./src/
COPY data/ ./data/

# Dash must listen on 0.0.0.0 inside a container so the host can reach it
ENV DASH_HOST=0.0.0.0
ENV DASH_PORT=8050
ENV DASH_DEBUG=false
ENV PYTHONPATH=/app/src

EXPOSE 8050

CMD ["python", "-m", "allocator.app"]
