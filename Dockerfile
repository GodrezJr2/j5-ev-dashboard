FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir requests websocket-client

COPY tools/ /app/tools/
COPY web/  /app/web/

ENV CARLINKO_DATA=/data
VOLUME /data
WORKDIR /app/tools
EXPOSE 8088

# Default = dashboard + logger together. Prefer separate services via docker-compose.yml
# when you want independent restart/logs (web / logger override this CMD).
CMD ["python", "entrypoint.py", "8088"]
