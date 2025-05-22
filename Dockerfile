# Use Ubuntu as base image
FROM ubuntu:20.04

# Avoid timezone prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set the environment variable
ENV IOTHUB_DEVICE_CONNECTION_STRING="HostName=H-ryhma-IoT-hub.azure-devices.net;DeviceId=device2;SharedAccessKey=RA7N4plT80RbehmWJlbZCrH/BySY+o5HIVmsMPadbH0="

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    nano \
    software-properties-common && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3.8.10
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.8 python3.8-dev python3.8-distutils && \
    rm -rf /var/lib/apt/lists/*

# Make Python 3.8 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1

# Install pip 20.0.2 for Python 3.8
RUN curl https://bootstrap.pypa.io/pip/3.8/get-pip.py -o get-pip.py && \
    python3 get-pip.py 'pip==20.0.2' && \
    rm get-pip.py

# Create symbolic links
RUN ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip

# Upgrade pip
RUN pip install --upgrade pip==23.0

# Install azure-iot-device and azure-storage-blob
RUN pip install azure-iot-device azure-storage-blob

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