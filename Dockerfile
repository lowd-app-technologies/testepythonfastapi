# Usa uma imagem base com Python otimizada
FROM python:3.10-slim

# Define variáveis de ambiente para otimização
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONHASHSEED=random \
    PYTHONUTF8=1 \
    TZ=UTC

# Configurações do Chrome para perfomance
ENV CHROME_NO_SANDBOX=1 \
    CHROMEDRIVER_WHITELISTED_IPS="" \
    PYTHONTRACEMALLOC=1 \
    PYTHONIOENCODING="utf-8"

# Instala dependências do sistema em uma única camada para reduzir o tamanho da imagem
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    gnupg \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    xdg-utils \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Baixa e instala o Google Chrome com hash de verificação
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Instala o ChromeDriver correspondente à versão do Chrome instalado
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1) && \
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") && \
    echo "Instalando ChromeDriver versão $CHROMEDRIVER_VERSION para Chrome $CHROME_VERSION" && \
    wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Define o diretório de trabalho
WORKDIR /app

# Copia apenas os arquivos de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto dos arquivos do projeto
COPY . .

# Verifica se o Chrome e o ChromeDriver foram instalados corretamente
RUN which google-chrome && google-chrome --version && \
    which chromedriver && chromedriver --version

# Cria um usuário não-root para executar a aplicação (segurança)
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app

# Muda para o usuário não-root
USER appuser

# Expõe a porta da API
EXPOSE 8080

# Configura logs do Uvicorn e limites de memória
ENV UVICORN_LOG_LEVEL="info" \
    UVICORN_ACCESS_LOG=1 \
    UVICORN_LOG_CONFIG="log_config.json" \
    PYTHONWARNINGS="ignore::DeprecationWarning" \
    CHROME_IGNORE_CERTIFICATE_ERRORS=1 \
    # Configurações para o gerenciamento de memória Python
    PYTHONMALLOC=malloc \
    # Limites para a JVM do Chrome 
    NODE_OPTIONS="--max-old-space-size=2048" \
    # Número de threads para o GC
    PYTHONGC="threads" \
    # Agressividade da coleta de lixo
    PYTHONGCTHRESHOLD=700 \
    # Forçar liberação de memória de volta ao sistema
    MALLOC_TRIM_THRESHOLD_=65536

# Arquivo para configurar os logs centralizados
COPY log_config.json /app/log_config.json

# Cria diretório para logs
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Cria diretório para screenshots de erro
RUN mkdir -p /app/screenshots && chown -R appuser:appuser /app/screenshots

# Comando para rodar a API com configurações otimizadas para WebSockets
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--workers", "1", \
     "--limit-concurrency", "50", \
     "--backlog", "2048", \
     "--timeout-keep-alive", "120", \
     "--log-level", "info", \
     "--ws", "auto", \
     "--loop", "auto", \
     "--http", "auto"]
