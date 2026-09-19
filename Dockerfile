FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir requests websocket-client

COPY tools/ /app/tools/
COPY web/  /app/web/

ENV CARLINKO_DATA=/data
# no VOLUME instruction: docker-compose mounts ./data:/data, Railway attaches its own volume
WORKDIR /app/tools
EXPOSE 8088

# Default = the dashboard, and nothing else. The logger runs as a second service
# (see docker-compose.yml). A single-service host that wants both in one container
# points its start command at `bash railway_start.sh` -- deliberately not the default,
# because CarLinko allows one live session per account and a plain `docker run` that
# quietly started a logger would knock the owner's own app offline.
CMD ["python", "server.py", "8088"]
