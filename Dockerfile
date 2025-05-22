# Use NVIDIA CUDA 12.8 devel with Ubuntu 22.04
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV SPCONV_ALGO=native
ENV TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0"

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -s /bin/bash gradio && \
    mkdir -p /app && \
    chown -R gradio:gradio /app

# Switch to non-root user
USER gradio

# Set working directory
WORKDIR /app

# Create virtual environment
RUN python3 -m venv venv

# Copy requirements first for better caching
COPY --chown=gradio:gradio requirements.txt .

# Install Python dependencies in venv
RUN . venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=gradio:gradio . .

# Create necessary directories
RUN mkdir -p /app/tmp

# Expose port for Gradio
EXPOSE 7860

# Set the default command
CMD ["./venv/bin/python", "app.py"]
