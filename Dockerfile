# Use Ubuntu as base image
FROM ubuntu:20.04

# Avoid timezone prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

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

# Install pip 20.0.2
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python3 get-pip.py 'pip==20.0.2' && \
    rm get-pip.py

# Create symbolic links
RUN ln -s /usr/bin/python3 /usr/bin/python && \
    ln -s /usr/bin/pip3 /usr/bin/pip

# Install azure-iot-device and verify installation
RUN pip install azure-iot-device && \
    python -c "from azure.iot.device import IoTHubDeviceClient; print('Azure IoT Device package successfully installed')"

# Verify all installations
RUN python --version && \
    pip --version && \
    nano --version

# Set working directory
WORKDIR /app

COPY simulate_temp_readings.py .

CMD ["tail", "-f", "/dev/null"]