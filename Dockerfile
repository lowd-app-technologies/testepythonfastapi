FROM python:3.10-slim

# Atualiza pacotes e instala dependências necessárias para o Chrome
RUN apt-get update && apt-get install -y \
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
    && rm -rf /var/lib/apt/lists/*

# Cria o diretório antes de mover o Chrome
RUN mkdir -p /opt/google/

# Baixa e instala o Google Chrome 134
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/134.0.6998.35/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/google/chrome && \
    ln -s /opt/google/chrome/chrome /usr/local/bin/google-chrome

# Baixa e instala o ChromeDriver 134
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/134.0.6998.35/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Verifica se o Chrome foi instalado corretamente
RUN which google-chrome && google-chrome --version

# Expõe a porta da API
EXPOSE 8080

# Comando para rodar a API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]