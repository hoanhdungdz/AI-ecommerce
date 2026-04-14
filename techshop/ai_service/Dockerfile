FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cài đặt build tools cho TensorFlow và các C extensions
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Tăng timeout để tránh đứt kết nối khi download TensorFlow (~500MB)
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .

# Tạo thư mục cho ChromaDB data
RUN mkdir -p /app/chroma_db /app/saved_model

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
