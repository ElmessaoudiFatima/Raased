FROM python:3.12-slim

WORKDIR /app

COPY flask_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn==23.0.0

COPY flask_api/ .

ENV DATABASE_URL=postgresql+psycopg://raased:raased@platform-db:5432/raased_platform
ENV AUTO_CREATE_DB=1
ENV AUTO_SEED=1

EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]