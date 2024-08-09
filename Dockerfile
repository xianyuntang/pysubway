FROM python:3.12.4 as python
ENV PYTHONUNBUFFERED=true

FROM python as poetry

ENV POETRY_HOME=/etc/poetry
ENV POETRY_VERSION=1.8.3
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN curl -sSL https://install.python-poetry.org | python -

FROM poetry as builder
WORKDIR /app
COPY pyproject.toml ./
COPY poetry.lock ./
RUN poetry install --without dev --no-interaction --no-ansi -vvv


FROM python
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
COPY . /app
COPY --from=builder /app/.venv /app/.venv
RUN mkdir ~/.subway/ssl