FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "sleep 5 && python manage.py makemigrations laptop_app && python manage.py migrate --noinput && python manage.py loaddata laptop_app/fixtures/initial_laptops.json && python manage.py runserver 0.0.0.0:8000"]
