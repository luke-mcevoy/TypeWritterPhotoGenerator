FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ascii_engine.py typewriter_engine.py db.py ./
COPY fonts ./fonts
COPY static ./static
COPY templates ./templates

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --timeout 180 --workers 1 --threads 2 app:app"]
