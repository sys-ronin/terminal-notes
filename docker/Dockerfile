FROM python:3.13-slim

# Install system packages including locales
RUN apt-get update && apt-get install -y \
    git \
    vim \
    nano \
    neovim \
    openssh-server \
    sudo \
    wget \
    ca-certificates \
    curl \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Generate locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen en_US.UTF-8

# Set locale environment variables
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Update CA certificates
RUN update-ca-certificates

# Install micro editor
RUN wget -O /tmp/micro.tar.gz https://github.com/zyedidia/micro/releases/download/v2.0.13/micro-2.0.13-linux64-static.tar.gz \
    && tar -xzf /tmp/micro.tar.gz -C /tmp \
    && mv /tmp/micro-*/micro /usr/local/bin/ \
    && chmod +x /usr/local/bin/micro \
    && rm -rf /tmp/micro*

# Install Python packages
RUN pip install --no-cache-dir requests urllib3 certifi

# Create SSH directory
RUN mkdir -p /etc/ssh /data/ssh

# Create user
RUN useradd -m -s /bin/bash tnuser && echo "tnuser:tnpass" | chpasswd

# Create necessary directories
RUN mkdir -p /app/source /data
ENV PYTHONPATH=/app/source
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Copy source code
COPY source/ /app/source/

# Set ownership and permissions
RUN chown -R tnuser:tnuser /app/source
RUN chmod +x /app/source/terminal_notes_ui.py
RUN chmod +x /app/source/git_filter_repo.py
RUN find /app/source -name "*.py" -exec chmod +x {} \;

# Set permissions for data directories
RUN chown -R tnuser:tnuser /data /home/tnuser

WORKDIR /app

# Copy and set entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose SSH port
EXPOSE 22

ENTRYPOINT ["/app/entrypoint.sh"]