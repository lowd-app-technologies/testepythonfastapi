# Usa uma imagem do Python oficial
FROM python:3.10

# Instala dependências do Chrome e Chromedriver
RUN apt update && apt install -y \
    google-chrome-stable \
    chromium-driver

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
