FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Đảm bảo entrypoint script có quyền thực thi
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Sử dụng entrypoint script (migrate + seed + runserver)
ENTRYPOINT ["/app/entrypoint.sh"]
