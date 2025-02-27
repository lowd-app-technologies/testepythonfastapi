# Usando uma imagem base do Python
FROM python:3.9-slim

# Instalar dependências do sistema
RUN apt-get update && \
    apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    chromium-driver \
    curl && \
    apt-get clean

# Definindo variáveis de ambiente para o Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV DISPLAY=:99

# Criar e definir o diretório de trabalho
WORKDIR /app

# Copiar o código da aplicação para o container
COPY . /app

# Instalar dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Expor a porta que o FastAPI vai rodar
EXPOSE 8000

# Comando para iniciar o servidor FastAPI com o Uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]