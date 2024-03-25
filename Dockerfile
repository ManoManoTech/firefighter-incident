FROM python:3.12-slim-bullseye

LABEL maintainer="tech-pe-pulse-team@manomano.com"
LABEL org.opencontainers.image.title="ManoManoTech"
LABEL org.opencontainers.image.description="FireFighter runtime image"
LABEL org.opencontainers.image.url="https://github.com/ManoManoTech/firefighter-incident/"
LABEL org.opencontainers.image.documentation="https://github.com/ManoManoTech/firefighter-incident/"
LABEL org.opencontainers.image.vendor="Colibri SAS"
LABEL org.opencontainers.image.authors="tech-pe-pulse-team@manomano.com"

# add our user and group first to make sure their IDs get assigned consistently
RUN groupadd -r firefighter && useradd -r -m -g firefighter firefighter

# Sane defaults for pip
ENV \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies first to leverage Docker layer caching.
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
  pip install -r /tmp/requirements.txt

RUN --mount=type=bind,source=dist,target=/tmp/app_dist \
  pip install /tmp/app_dist/*.whl --no-deps && pip check

EXPOSE 8000
VOLUME /data
WORKDIR /var/app

# We don't have the dev dependencies in the image
ENV ENV=prod
ENV DEBUG=False

USER firefighter
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["ff-web"]

LABEL org.opencontainers.image.source="https://github.com/ManoManoTech/firefighter-incident/tree/${SOURCE_COMMIT:-master}/"
LABEL org.opencontainers.image.licenses="https://github.com/ManoManoTech/firefighter-incident/blob/${SOURCE_COMMIT:-master}/LICENSE"
