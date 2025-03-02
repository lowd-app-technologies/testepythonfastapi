#!/bin/bash
set -e

# Imprimir informações de diagnóstico
echo "📊 Iniciando aplicação FastAPI com Instagram Bot..."
echo "💻 Versão do Python: $(python3 --version)"
echo "🔍 Verificando Chrome e ChromeDriver..."
which google-chrome && google-chrome --version
which chromedriver && chromedriver --version

# Verificar diretórios necessários
echo "📁 Verificando diretórios de logs e screenshots..."
mkdir -p /app/logs
mkdir -p /app/screenshots
chmod -R 755 /app/logs /app/screenshots

# Rodar o garbage collector antes de iniciar
echo "🧹 Executando limpeza de memória inicial..."
python3 -c "import gc; gc.collect()"

# Função para lidar com o encerramento
graceful_shutdown() {
  echo "🛑 Recebido sinal para encerrar aplicação. Encerrando graciosamente..."
  # Aqui você pode adicionar lógica para encerrar recursos de forma limpa
  exit 0
}

# Configurar handler para SIGTERM e SIGINT
trap graceful_shutdown SIGTERM SIGINT

# Iniciar a aplicação
echo "🚀 Iniciando servidor..."
exec uvicorn main:app --host 0.0.0.0 --port 8080 \
  --workers 1 \
  --limit-concurrency 50 \
  --backlog 2048 \
  --timeout-keep-alive 120 \
  --log-level info \
  --ws auto \
  --loop auto \
  --http auto
