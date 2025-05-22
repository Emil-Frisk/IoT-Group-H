FROM python:3.11-slim-bullseye as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    pkg-config \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Upgrade pip and install wheel
RUN pip install --upgrade pip setuptools wheel

# Build and install the packages
RUN pip install --no-cache-dir \
    --prefer-binary \
    cryptography==41.0.7 \
    azure-iot-device==2.14.0 \
    azure-storage-blob==12.25.1

# Final stage - runtime image
FROM python:3.11-slim-bullseye

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application script
COPY simulate_temp_readings.py .

# Verify installations
RUN python --version && \
    pip --version && \
    nano --version

# Keep container running
CMD ["tail", "-f", "/dev/null"]