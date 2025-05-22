# Use Ubuntu 20.04 as base image
FROM ubuntu:20.04

# Avoid timezone prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set the environment variable

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    nano \
    software-properties-common && \
    rm -rf /var/lib/apt/lists/*

# Add deadsnakes PPA to install Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.11 python3.11-dev python3.11-distutils && \
    rm -rf /var/lib/apt/lists/*

# Make Python 3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install pip for Python 3.11
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python3 get-pip.py 'pip==23.0' && \
    rm get-pip.py

# Create symbolic links
RUN ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip

# Install azure-iot-device and azure-storage-blob with pinned versions
RUN pip install cryptography azure-iot-device azure-storage-blob 

# Verify all installations
RUN python --version && \
    pip --version && \
    nano --version

# Set working directory
WORKDIR /app

# Copy application script
COPY simulate_temp_readings.py .

# Keep container running
CMD ["tail", "-f", "/dev/null"]