FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed && gunicorn config.wsgi:application -b 0.0.0.0:8000"]
