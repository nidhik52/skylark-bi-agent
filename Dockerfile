FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

EXPOSE 8000

# Railway injects $PORT; fall back to 8000 locally
CMD ["sh", "-c", "python -m chainlit run app.py --host 0.0.0.0 --port ${PORT:-8000}"]
