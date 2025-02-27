# Usa uma imagem do Python oficial
FROM python:3.10

# Atualiza pacotes e instala dependências básicas
RUN apt update && apt install -y \
    curl \
    unzip \
    gnupg \
    wget

# Adiciona a chave e o repositório do Google Chrome
RUN wget -qO- https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt update && \
    apt install -y google-chrome-stable

# Instala o ChromeDriver compatível
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION") && \
    wget -q "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    rm /tmp/chromedriver.zip

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto para o container
COPY . .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Define a porta que o Railway usará
ENV PORT=8000

# Expõe a porta
EXPOSE 8000

# Comando para rodar o servidor FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
