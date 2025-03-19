# Usa uma imagem base com Python
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

# Baixa e instala o Google Chrome
# Adiciona o repositório do Google Chrome e instala o Chrome corretamente
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable


# Instala o ChromeDriver
RUN wget -q https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver

RUN apt-get update && apt-get install -y google-chrome-stable
    
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
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8080", "main:app"]