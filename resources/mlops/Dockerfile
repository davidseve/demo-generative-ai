FROM registry.redhat.io/ubi9/python-311:latest

WORKDIR /app

# Install system dependencies
RUN yum update && yum -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy pipeline source code (if needed)
COPY pipeline.py .

ENTRYPOINT ["python"]
CMD ["pipeline.py"]