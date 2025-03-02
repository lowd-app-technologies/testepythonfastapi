# FastAPI Instagram Bot

API robusta para automação de processos no Instagram usando FastAPI, Python, Selenium e WebSockets.

## 🛠 Recursos e Otimizações

### Recursos Principais
- **Automação de Instagram via Selenium**: Login automático e adição de usuários a Close Friends
- **WebSockets**: Comunicação em tempo real com o cliente durante a execução de operações
- **Tratamento de Erros Avançado**: Retry automático para operações críticas
- **Monitoramento de Memória**: Verificação e otimização de uso de memória
- **Logging Estruturado**: Sistema de logs detalhados com emojis para melhor legibilidade
- **Capturas de Tela Automáticas**: Screenshots de erros com informações contextuais
- **Endpoint de Status**: Monitoramento do estado do sistema e uso de recursos

### Otimizações
- **Estabilidade**: Retry automático para operações falhas
- **Gerenciamento de Recursos**: Garbage collection e monitoramento de memória
- **Segurança**: Execução com usuário não-root no Docker
- **Graceful Shutdown**: Encerramento correto dos processos durante desligamento

## 📊 Monitorando o Sistema

A aplicação disponibiliza um endpoint `/status` para verificar o estado do sistema em tempo real:

```bash
curl http://localhost:8080/status
```

Este endpoint fornece informações detalhadas sobre:
- Uso de memória
- Uso de CPU
- Número de threads
- Tempo de execução
- Screenshots disponíveis para depuração
- Estado do garbage collector

## 🐳 Utilizando o Docker

Este projeto está completamente containerizado e otimizado para execução em Docker:

```bash
# Construir a imagem Docker
docker build -t instagram-bot-api .

# Executar o container
docker run -p 8080:8080 instagram-bot-api
```

## 🚀 API Endpoints

### WebSocket
- `/ws`: Endpoint WebSocket para comunicação em tempo real durante o processo de automação

### REST API
- `/status`: Verifica o estado do sistema e uso de recursos
- `/version`: Retorna a versão atual da aplicação
- `/stop`: Interrompe qualquer processo em execução

## 🔧 Configuração e Instalação Local

### Requisitos
- Python 3.8+
- Chrome instalado
- ChromeDriver compatível

### Instalação
```bash
# Instalar dependências
pip install -r requirements.txt

# Executar a aplicação
uvicorn main:app --host 0.0.0.0 --port 8080
```

## 📝 Estrutura de Logs

Os logs são gerados em vários formatos:
- Console (com emojis para melhor legibilidade)
- Arquivos de log com rotação (`/app/logs/`)
- Screenshots de erros (`/app/screenshots/`)

## 🔒 Segurança

- Uso de `undetected_chromedriver` para evitar detecção pelo Instagram
- Execução com usuário não-privilegiado no Docker
- Não armazena credenciais sensíveis

## 🔄 CI/CD

Este projeto está preparado para deploy contínuo em plataformas como Railway:
- Optimizado para deploy em CI/CD
- Docker multi-stage build para reduzir tamanho da imagem final
- Script de entrypoint para inicialização e monitoramento
