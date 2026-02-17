FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        nano \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files needed for build
COPY uv.lock pyproject.toml cli.py README.md ./

# Copy submodule for pyetera_uart_bridge
COPY etera-uart-bridge/pyetera-uart-bridge/pyetera-uart-bridge/ \
     etera-uart-bridge/pyetera-uart-bridge/pyetera-uart-bridge/

# Copy source code and recreate the symlink that points to the submodule
COPY kronoterm2mqtt/ kronoterm2mqtt/
RUN rm -rf kronoterm2mqtt/pyetera_uart_bridge && \
    ln -s ../etera-uart-bridge/pyetera-uart-bridge/pyetera-uart-bridge \
          kronoterm2mqtt/pyetera_uart_bridge

# Bootstrap: create venv and install dependencies
RUN python3 cli.py --help

ENTRYPOINT ["python3", "cli.py"]
CMD ["publish-loop"]
