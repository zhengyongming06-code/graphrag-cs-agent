FROM python:3.11-slim

WORKDIR /srv

COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

COPY backend /srv/backend
COPY data /srv/data
COPY eval /srv/eval

ENV PYTHONPATH=/srv/backend
ENV PYTHONUNBUFFERED=1

WORKDIR /srv/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
