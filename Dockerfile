FROM python:3.14-alpine AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN rm -rf /usr/local/lib/python3.14/idlelib \
           /usr/local/lib/python3.14/tkinter \
           /usr/local/lib/python3.14/ensurepip \
           /usr/local/lib/python3.14/pydoc_data \
           /usr/local/lib/python3.14/turtledemo \
           /usr/local/lib/python3.14/multiprocessing \
           /usr/local/lib/python3.14/doctest.py \
           /usr/local/lib/python3.14/pdb.py \
           /usr/local/lib/python3.14/turtle.py \
           /usr/local/lib/python3.14/site-packages/pip* \
           /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
           /var/cache/apk/*
WORKDIR /app
ARG BUILD_DATE
RUN echo "$BUILD_DATE" > /app/build_date.txt
COPY pyproject.toml uv.lock ./
RUN apk add --no-cache upx \
 && uv sync --frozen --no-dev \
 && find /app/.venv -name '*.so' -exec upx --lzma {} + 2>/dev/null || true \
 && uv cache clean \
 && rm -f /bin/uv /bin/uvx \
 && apk del upx
COPY bot/ bot/
COPY BIDE.md .

FROM scratch
COPY --from=builder / /
ENV PATH=/app/.venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV PYTHONPATH=/app/.venv/lib/python3.14/site-packages:$PYTHONPATH
WORKDIR /app
CMD ["python", "-m", "bot.main"]
