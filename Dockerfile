FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY migrations ./migrations
COPY jurisdictions ./jurisdictions
COPY agencies ./agencies
COPY clients ./clients
COPY fixtures ./fixtures
COPY ["PRORRATEO MASTER.xlsx", "./PRORRATEO MASTER.xlsx"]
COPY scripts ./scripts

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
