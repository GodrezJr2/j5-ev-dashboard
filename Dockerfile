FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir requests websocket-client

COPY tools/ /app/tools/
COPY web/  /app/web/

ENV CARLINKO_DATA=/data
# no VOLUME instruction: docker-compose mounts ./data:/data, Railway attaches its own volume
WORKDIR /app/tools
EXPOSE 8088

# Default = dashboard + logger in one container (single-service hosts like Railway;
# writes /data/creds.json from $CREDS_JSON if set). docker-compose overrides this
# per service (see docker-compose.yml), so compose behavior is unchanged.
CMD ["bash", "railway_start.sh"]
