FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN mkdir -p /app/data/media

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
