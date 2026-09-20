FROM ubuntu:22.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 mesa-utils && rm -rf /var/lib/apt/lists/*
COPY cuda_smoke.py /opt/cuda_smoke.py
CMD ["python3", "/opt/cuda_smoke.py"]
