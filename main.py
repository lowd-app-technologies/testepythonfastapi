from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import asyncio
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
import logging
import traceback
import gc
import psutil
import sys
import os
import json
import pickle
from datetime import datetime

# Importar Tenacity para retentativas automáticas
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configurar FastAPI com melhores configurações para operações de longa duração
# e melhor gerenciamento de recursos
app = FastAPI(
    title="Instagram Close Friends Manager",
    description="API para gerenciar automaticamente lista de Close Friends no Instagram",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuração do servidor para melhor desempenho em operações de longa duração
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        workers=1,  # Para aplicações com WebSocket é melhor usar um único worker
        timeout_keep_alive=120,  # Manter conexões ativas por mais tempo
        log_level="info"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

class Credentials(BaseModel):
    username: str
    password: str
    use_saved_session: bool = True  # Por padrão, tenta usar sessão salva

stop_process = False 

# Diretório para armazenar cookies e dados de sessão
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)

# Configurar o logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

def log_emoji(logger, level, message, emoji='📝'):
    """
    Função de logging com emojis personalizados
    
    Níveis de log suportados:
    - info: 🌐 (globo)
    - warning: ⚠️ (aviso)
    - error: 💥 (explosão)
    - critical: 🚨 (sirene)
    - debug: 🔍 (lupa)
    
    Uso:
    log_emoji(logger, 'info', 'Mensagem de log')
    """
    emoji_map = {
        'info': '🌐',
        'warning': '⚠️',
        'error': '💥',
        'critical': '🚨',
        'debug': '🔍'
    }
    
    # Usar emoji personalizado ou do mapeamento
    emoji = emoji_map.get(level.lower(), emoji)
    
    # Formatar mensagem com emoji
    emoji_message = f"{emoji} {message}"
    
    # Chamar o método de log correspondente
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(emoji_message)

# Funções com retry automático para operações críticas
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), 
       retry=retry_if_exception_type((StaleElementReferenceException, NoSuchElementException, TimeoutException)))
def safe_find_element(driver, by, value, timeout=10):
    """Função que busca um elemento com retry automático"""
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_element_located((by, value)))

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((StaleElementReferenceException, NoSuchElementException, TimeoutException)))
def safe_find_elements(driver, by, value, timeout=10):
    """Função que busca elementos com retry automático"""
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_all_elements_located((by, value)))

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((StaleElementReferenceException, NoSuchElementException)))
def safe_click(element):
    """Função que clica em um elemento com retry automático"""
    element.click()
    return True

# Função para monitorar memória
def check_memory_usage():
    """Monitora o uso de memória do processo atual"""
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    return memory_mb

# Função para verificar se existe uma sessão salva válida
async def check_saved_session(username: str, websocket: WebSocket):
    """
    Verifica se existe uma sessão salva válida e tenta utilizá-la.
    Retorna (True, driver) se a sessão for válida, (False, None) caso contrário.
    """
    session_path = os.path.join(SESSION_DIR, f"{username}_cookies.pkl")
    metadata_path = os.path.join(SESSION_DIR, f"{username}_metadata.json")
    
    # Verificar se os arquivos existem
    if not (os.path.exists(session_path) and os.path.exists(metadata_path)):
        log_emoji(logger, 'info', f'Não foi encontrada sessão salva para {username[:3]}***')
        return False, None
    
    # Verificar metadados da sessão
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Verificar data da última sessão
        last_login = datetime.fromisoformat(metadata['last_login'])
        current_time = datetime.now()
        session_age = (current_time - last_login).total_seconds() / 3600  # em horas
        
        log_emoji(logger, 'info', f'Sessão encontrada, idade: {session_age:.1f} horas')
        await websocket.send_text(f"Encontrada sessão salva de {session_age:.1f} horas atrás")
        
        # Se a sessão for muito antiga (mais de 48 horas), invalidá-la
        if session_age > 48:
            log_emoji(logger, 'info', f'Sessão muito antiga ({session_age:.1f} horas), será ignorada')
            await websocket.send_text("A sessão salva é muito antiga. Iniciando nova autenticação...")
            return False, None
        
        # Tentar usar a sessão salva
        log_emoji(logger, 'info', 'Tentando carregar sessão salva...')
        await websocket.send_text("Tentando restaurar sessão...")
        
        try:
            # Inicializar driver
            log_emoji(logger, 'info', 'Inicializando driver para sessão salva')
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-features=NetworkService')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--blink-settings=imagesEnabled=true')
            
            driver = uc.Chrome(options=options, headless=True)
            driver.set_page_load_timeout(30)
            
            # Abrir Instagram e carregar cookies
            driver.get("https://www.instagram.com/")
            await asyncio.sleep(2)
            
            # Carregar cookies
            with open(session_path, 'rb') as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception:
                        pass
            
            # Recarregar após adicionar cookies
            driver.refresh()
            await asyncio.sleep(3)
            
            # Verificar se a sessão é válida
            try:
                # Verificar se estamos logados
                wait = WebDriverWait(driver, 10)
                profile_icon = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//span[contains(@class, 'coreSpriteProfilePic')]/.." + 
                              " | //span[contains(@class, 'xp7jhwk')]/.." +
                              " | //div[contains(@class, '_aarf')]/.." +
                              " | //div[contains(@data-bloks-name, 'ig.components.ProfilePicture')]/..")
                ))
                
                log_emoji(logger, 'info', 'Sessão restaurada com sucesso')
                await websocket.send_text("✅ Sessão restaurada com sucesso!")
                
                # Atualizar metadados da sessão
                update_session_metadata(username)
                
                return True, driver
                
            except Exception as e:
                log_emoji(logger, 'warning', f'Falha ao verificar sessão: {str(e)}')
                await websocket.send_text("Sessão expirada ou inválida. Iniciando nova autenticação...")
                driver.quit()
                return False, None
                
        except Exception as session_error:
            log_emoji(logger, 'error', f'Erro ao carregar sessão: {str(session_error)}')
            await websocket.send_text("Falha ao restaurar sessão. Iniciando nova autenticação...")
            if 'driver' in locals() and driver:
                driver.quit()
            return False, None
            
    except Exception as metadata_error:
        log_emoji(logger, 'error', f'Erro ao ler metadados da sessão: {str(metadata_error)}')
        return False, None

# Função para salvar cookies e metadados da sessão
def save_session(driver, username):
    """
    Salva os cookies e metadados da sessão para uso futuro.
    """
    try:
        # Criar diretório para sessões se não existir
        os.makedirs(SESSION_DIR, exist_ok=True)
        
        # Salvar cookies
        cookies_path = os.path.join(SESSION_DIR, f"{username}_cookies.pkl")
        with open(cookies_path, 'wb') as f:
            pickle.dump(driver.get_cookies(), f)
        
        # Salvar metadados
        metadata_path = os.path.join(SESSION_DIR, f"{username}_metadata.json")
        metadata = {
            'last_login': datetime.now().isoformat(),
            'browser_version': driver.capabilities.get('browserVersion', 'unknown'),
            'user_agent': driver.execute_script("return navigator.userAgent;"),
            'resolution': {
                'width': driver.execute_script("return window.innerWidth;"),
                'height': driver.execute_script("return window.innerHeight;")
            }
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
            
        log_emoji(logger, 'info', f'Sessão salva com sucesso para {username[:3]}***')
        return True
    except Exception as e:
        log_emoji(logger, 'error', f'Erro ao salvar sessão: {str(e)}')
        return False

# Função para atualizar os metadados da sessão
def update_session_metadata(username):
    """
    Atualiza a data de último acesso nos metadados da sessão.
    """
    try:
        metadata_path = os.path.join(SESSION_DIR, f"{username}_metadata.json")
        
        # Carregar metadados existentes
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Atualizar timestamp
        metadata['last_login'] = datetime.now().isoformat()
        
        # Salvar metadados atualizados
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
            
        return True
    except Exception as e:
        log_emoji(logger, 'error', f'Erro ao atualizar metadados da sessão: {str(e)}')
        return False

def capture_error_screenshot(driver, error_name, context_info=""):
    """Captura screenshot com informações detalhadas do erro
    
    Args:
        driver: Driver do Selenium
        error_name: Nome descritivo do erro
        context_info: Informações adicionais sobre o contexto do erro
    
    Returns:
        str: Caminho do arquivo de screenshot ou None se falhar
    """
    try:
        # Certificar-se de que o diretório de screenshots existe
        import os
        screenshots_dir = os.path.join(os.getcwd(), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Adicionar timestamp ao nome do arquivo
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{screenshots_dir}/{error_name}_{timestamp}.png"
        
        # Capturar informações do DOM para fins de depuração
        page_source = ""
        try:
            page_source = driver.page_source
            with open(f"{screenshots_dir}/{error_name}_{timestamp}_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
        except:
            pass
        
        # Capturar screenshot
        driver.save_screenshot(filename)
        
        # Registrar informações do erro
        log_emoji(logger, 'info', f'Screenshot capturado: {filename}')
        log_emoji(logger, 'info', f'Contexto do erro: {context_info}')
        
        # Salvar informações de URL e título da página
        try:
            with open(f"{screenshots_dir}/{error_name}_{timestamp}_info.txt", "w", encoding="utf-8") as f:
                f.write(f"URL: {driver.current_url}\n")
                f.write(f"Título: {driver.title}\n")
                f.write(f"Contexto: {context_info}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Memória em uso: {check_memory_usage():.2f} MB\n")
        except:
            pass
            
        return filename
    except Exception as e:
        log_emoji(logger, 'error', f'Falha ao capturar screenshot: {str(e)}')
        return None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global stop_process
    stop_process = False  
    driver = None
    start_time = time.time()
    start_memory = check_memory_usage()
    
    log_emoji(logger, 'info', f'Nova conexão WebSocket iniciada. Memória inicial: {start_memory:.2f} MB')
    
    await websocket.accept()
    try:
        try:
            log_emoji(logger, 'info', 'Aguardando credenciais do usuário')
            data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            username = data.get("username")
            password = data.get("password")
            use_saved_session = data.get("use_saved_session", True)  # Por padrão, tenta usar sessão salva
            
            if not username or not password:
                raise ValueError("Nome de usuário e senha são obrigatórios")
            
            log_emoji(logger, 'info', f'Credenciais recebidas para o usuário: {username[:3]}***')
            log_emoji(logger, 'info', f'Usar sessão salva: {use_saved_session}')
            
        except asyncio.TimeoutError:
            log_emoji(logger, 'error', 'Timeout ao receber credenciais')
            await websocket.send_text("⚠️ Timeout ao receber credenciais. Por favor, tente novamente.")
            return
        except Exception as e:
            log_emoji(logger, 'error', f'Erro ao processar dados de entrada: {str(e)}')
            await websocket.send_text(f"❌ Erro ao processar dados de entrada: {str(e)}")
            return

        try:
            # Verificar se deve tentar usar sessão salva
            session_valid = False
            if use_saved_session:
                log_emoji(logger, 'info', f'Tentando usar sessão salva para {username[:3]}***')
                await websocket.send_text("Verificando sessão salva...")
                session_valid, driver = await check_saved_session(username, websocket)
            
            # Se não existe sessão válida, fazer login normal
            if not session_valid:
                # Monitorar memória antes da autenticação
                pre_auth_memory = check_memory_usage()
                log_emoji(logger, 'info', f'Memória antes da autenticação: {pre_auth_memory:.2f} MB')
                
                log_emoji(logger, 'info', 'Iniciando autenticação...')
                await websocket.send_text("🔑 Iniciando autenticação...")
                
                # Registrar inicio da autenticação
                auth_start_time = time.time()
                log_emoji(logger, 'info', 'Chamando função de autenticação...')
                await websocket.send_text("Iniciando processo de autenticação...")
                
                # Tentar autenticar
                driver = authenticate(username, password)
                auth_duration = time.time() - auth_start_time
                log_emoji(logger, 'info', f'Autenticação concluída em {auth_duration:.2f} segundos')
                
                # Salvar cookies e sessão após autenticação bem-sucedida
                save_session(driver, username)
                log_emoji(logger, 'info', f'Sessão salva com sucesso para {username[:3]}***')
                await websocket.send_text("Sessão salva para uso futuro!")
        except Exception as auth_error:
            # Limpar recursos
            driver.quit() if driver else None
            gc.collect()
            
            # Obter o traceback para registro
            error_tb = traceback.format_exc()
            log_emoji(logger, 'error', f'Falha na autenticação: {str(auth_error)}')
            log_emoji(logger, 'error', f'Traceback completo:\n{error_tb}')
            
            # Verificar se é um erro relacionado a 2FA
            error_msg = str(auth_error).lower()
            if any(term in error_msg for term in ['two factor', '2fa', 'verificar', 'verificação', 'verification']):
                await websocket.send_text(f"⚠️ REQUER VERIFICAÇÃO: A conta parece exigir verificação em duas etapas.\n\n" +
                                         f"Por favor:\n" +
                                         f"1. Faça login manualmente no Instagram\n" +
                                         f"2. Complete a verificação de segurança, se solicitada\n" +
                                         f"3. Tente novamente após confirmar que pode acessar sua conta")
            # Verificar se parece ser um erro de credenciais
            elif any(term in error_msg for term in ['incorrect', 'senha inv', 'credencial', 'password', 'username']):
                await websocket.send_text(f"❌ CREDENCIAIS INVÁLIDAS: Não foi possível fazer login no Instagram.\n\n" +
                                         f"Verifique:\n" +
                                         f"- Se o nome de usuário e senha estão corretos\n" +
                                         f"- Se sua conta não está temporariamente bloqueada\n" +
                                         f"- Se você não precisa verificar sua conta manualmente")
            # Verificar se é um erro de RetryError específico
            elif 'retryerror' in error_msg or '<future at' in error_msg:  # RetryError[<Future at 0x... state=finished raised TimeoutException>]
                await websocket.send_text(f"⏰ TENTATIVAS ESGOTADAS: O sistema tentou várias vezes, mas não conseguiu completar a operação.\n\n" +
                                         f"Detalhes:\n" +
                                         f"- O Instagram não respondeu após múltiplas tentativas\n" +
                                         f"- Possível detecção de automação ou bloqueio temporário\n\n" +
                                         f"Recomendações:\n" +
                                         f"- Aguarde pelo menos 30 minutos antes de tentar novamente\n" +
                                         f"- Tente fazer login manualmente no seu navegador\n" +
                                         f"- Verifique se há alguma notificação de segurança do Instagram")
            # Verificar se é um erro de timeout genérico
            elif any(term in error_msg for term in ['timeout', 'tempo esgotado', 'retry', 'tentat']):
                await websocket.send_text(f"⏱️ TEMPO ESGOTADO: O Instagram demorou muito para responder.\n\n" +
                                         f"Possíveis causas:\n" +
                                         f"- Conexão lenta com a internet\n" +
                                         f"- O Instagram está detectando automação\n" +
                                         f"- O sistema está sobrecarregado\n\n" +
                                         f"Dica: Tente novamente mais tarde ou verifique sua conta manualmente.")
            # Verificar se é erro de detecção de bot
            elif any(term in error_msg for term in ['bot', 'detect', 'challenge', 'suspicious', 'suspeita']):
                await websocket.send_text(f"⚠️ DETECÇÃO DE AUTOMAÇÃO: O Instagram detectou atividade suspeita.\n\n" +
                                         f"Possíveis causas:\n" +
                                         f"- Muitas tentativas de login recentes\n" +
                                         f"- Acesso a partir de um novo local/IP\n" +
                                         f"- Conta sob verificação de segurança\n\n" +
                                         f"Recomendações:\n" +
                                         f"- Faça login manualmente pelo navegador\n" +
                                         f"- Complete quaisquer verificações de segurança solicitadas\n" +
                                         f"- Espere algumas horas antes de tentar novamente")
            # Erro genérico
            else:
                # Formatar a mensagem de erro para melhor legibilidade
                formatted_error = str(auth_error).replace('\n', '\n  ')
                await websocket.send_text(f"❌ FALHA NA AUTENTICAÇÃO:\n  {formatted_error}\n\n" +
                                         f"Verifique os logs e screenshots para mais detalhes.")
            return
        
        # Monitorar memória após autenticação
        post_auth_memory = check_memory_usage()
        pre_auth_memory = check_memory_usage() if 'pre_auth_memory' not in locals() else pre_auth_memory
        log_emoji(logger, 'info', f'Memória após autenticação: {post_auth_memory:.2f} MB (delta: {post_auth_memory - pre_auth_memory:.2f} MB)')
            
        log_emoji(logger, 'info', 'Autenticação bem-sucedida!')
        await websocket.send_text("✅ Autenticação bem-sucedida! Adicionando usuários ao Close Friends...")

        try:
            # Estabelecer um timeout global para o processo
            total_adicionados = await asyncio.wait_for(
                add_users_to_close_friends(driver, websocket),
                timeout=3600  # 1 hora de timeout máximo
            )
            
            # Monitorar memória após processamento
            end_memory = check_memory_usage()
            log_emoji(logger, 'info', f'Memória após processamento: {end_memory:.2f} MB (delta total: {end_memory - start_memory:.2f} MB)')
            
            process_time = time.time() - start_time
            log_emoji(logger, 'info', f'Processo concluído em {process_time:.1f} segundos. {total_adicionados} usuários adicionados.')
            await websocket.send_text(f"🎉 Processo concluído! {total_adicionados} usuários adicionados ao Close Friends em {process_time/60:.1f} minutos.")
        except asyncio.TimeoutError:
            log_emoji(logger, 'error', 'O processo excedeu o tempo limite máximo (1 hora)')
            await websocket.send_text("⏰ O processo excedeu o tempo limite máximo de 1 hora. Por favor, divida o processamento em partes menores.")
        except Exception as process_error:
            log_emoji(logger, 'error', f'Erro durante o processamento: {str(process_error)}')
            await websocket.send_text(f"🚨 Erro durante o processamento: {str(process_error)}")
            # Registrar o traceback para depuração
            error_traceback = traceback.format_exc()
            log_emoji(logger, 'error', f'Detalhes do erro:\n{error_traceback}')
    except Exception as e:
        log_emoji(logger, 'error', f'Erro global: {str(e)}')
        await websocket.send_text(f"💥 Erro global: {str(e)}")
    finally:
        # Garantir que o driver é fechado corretamente
        if driver:
            log_emoji(logger, 'info', 'Fechando o navegador...')
            try:
                driver.quit()
                log_emoji(logger, 'info', 'Navegador fechado com sucesso')
            except Exception as driver_error:
                log_emoji(logger, 'warning', f'Erro ao fechar navegador: {str(driver_error)}')
            driver = None
        
        # Forçar coleta de lixo para liberar memória
        gc.collect()
        end_memory_after_gc = check_memory_usage()
        mem_freed = end_memory_after_gc - (end_memory if 'end_memory' in locals() else check_memory_usage())
        log_emoji(logger, 'info', f'Memória após GC: {end_memory_after_gc:.2f} MB (memória liberada: {-mem_freed:.2f} MB)')
        
        # Fechar a conexão websocket
        try:
            log_emoji(logger, 'info', 'Fechando conexão WebSocket')
            await websocket.close()
        except Exception as ws_close_error:
            log_emoji(logger, 'warning', f'Erro ao fechar WebSocket: {str(ws_close_error)}')
            
        log_emoji(logger, 'info', f'Sessão finalizada. Tempo total: {(time.time() - start_time)/60:.2f} minutos')

@app.post("/stop")
async def stop_process_api():
    global stop_process
    stop_process = True  

    
    return {"message": "Processo interrompido!"}

def authenticate(username: str, password: str):
    log_emoji(logger, 'info', 'Configurando opções do Chrome para autenticação')
    
    options = uc.ChromeOptions()
    # Em ambientes de produção considera usar sem headless para evitar detecção
    # O Instagram frequentemente detecta navegadores headless
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled") 
    
    # Adicionar user-agent realista
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Adicionar mais memória para o Chrome
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-notifications")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--window-size=1920,1080")  # Tamanho de tela realista
    
    # Remover o argumento single-process que pode causar problemas
    # options.add_argument("--process-per-site")
    # options.add_argument("--single-process")
    
    # Parâmetros para evitar detecção de automação
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-popup-blocking")
    
    # Configurações adicionais anti-detecção
    options.add_argument("--disable-automation")
    options.add_argument("--disable-blink-features")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # Tentar criar o driver com tentativas em caso de falha
    max_retries = 3
    retry_count = 0
    driver = None
    
    log_emoji(logger, 'info', 'Inicializando o navegador')
    
    while retry_count < max_retries:
        try:
            driver = uc.Chrome(options=options)
            log_emoji(logger, 'info', 'Navegador inicializado com sucesso')
            break
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                log_emoji(logger, 'error', f'Falha ao iniciar o navegador após {max_retries} tentativas')
                raise Exception(f"Falha ao iniciar o navegador após {max_retries} tentativas: {str(e)}")
            log_emoji(logger, 'warning', f'Tentativa {retry_count} de inicializar o navegador falhou, tentando novamente')
            time.sleep(2)  # Espera antes de tentar novamente

    try:
        # Monitorar uso de memória
        mem_before = check_memory_usage()
        log_emoji(logger, 'info', f'Memória antes da autenticação: {mem_before:.2f} MB')
        
        # Definir timeout de página explícito
        driver.set_page_load_timeout(30)
        log_emoji(logger, 'info', 'Navegando para Instagram')
        driver.get("https://www.instagram.com/")
        
        try:
            # Usar nossas funções com retry para buscar os elementos de login
            log_emoji(logger, 'info', 'Buscando os campos de login')
            username_input = safe_find_element(driver, By.NAME, "username", timeout=20)
            password_input = safe_find_element(driver, By.NAME, "password", timeout=10)
            
            # Simular comportamento humano ao preencher os campos
            log_emoji(logger, 'info', 'Preenchendo credenciais com comportamento humano')
            
            # Limpar campos
            username_input.clear()
            password_input.clear()
            
            # Função para digitar como humano
            def type_like_human(element, text):
                for char in text:
                    element.send_keys(char)
                    # Pausa aleatória entre digitações
                    time.sleep(random.uniform(0.05, 0.2))
                # Pausa aleatória após completar a digitação
                time.sleep(random.uniform(0.5, 1.5))
            
            # Digitar usuário e senha
            type_like_human(username_input, username)
            time.sleep(random.uniform(0.5, 1.5))  # Pausa realista entre campos
            type_like_human(password_input, password)
            
            # Pausa antes de enviar o formulário
            time.sleep(random.uniform(0.5, 2))
            
            # Enviar o formulário
            log_emoji(logger, 'info', 'Enviando formulário de login')
            # Tentar clicar no botão de login em vez de pressionar enter
            try:
                login_button = safe_find_element(driver, By.XPATH, "//button[@type='submit']", timeout=5)
                login_button.click()
            except Exception:
                log_emoji(logger, 'info', 'Botão de login não encontrado, usando pressionar Enter')
                password_input.send_keys(Keys.RETURN)
            
            # Esperar o login com nossa função com retry
            log_emoji(logger, 'info', 'Aguardando confirmação de login')
            
            # Adicionar atraso aleatório para simular comportamento humano
            import random
            time.sleep(random.uniform(1, 3))
            
            # Usar múltiplos seletores para tentar detectar o login bem-sucedido
            try:
                # Primeiro tentamos o seletor original
                safe_find_element(driver, By.XPATH, "//div[@role='dialog' or @role='main']", timeout=15)
            except Exception as e1:
                log_emoji(logger, 'warning', f'Primeiro seletor falhou: {str(e1)}')
                try:
                    # Verificar se estamos na página principal do Instagram
                    if 'instagram.com/accounts/onetap' in driver.current_url or 'instagram.com/?next=' in driver.current_url:
                        log_emoji(logger, 'info', 'Detectada página de redirecionamento pós-login')
                        pass  # Estamos em uma página pós-login conhecida
                    else:
                        # Tentar seletores alternativos
                        alt_selectors = [
                            "//a[@href='/direct/inbox/']",  # Link para mensagens diretas
                            "//span[contains(text(), 'Search')]",  # Busca (em inglês)
                            "//span[contains(text(), 'Pesquisar')]",  # Busca (em português)
                            "//div[@aria-label='Home' or @aria-label='Página inicial']",  # Botão Home
                            "//svg[@aria-label='Home']",  # Ícone Home
                            "//button[contains(text(), 'Not Now') or contains(text(), 'Agora não')]",  # Dialogo "Not Now"
                            "//div[contains(@class, 'x9f619')]",  # Classe comum nos elementos da interface principal
                            "//div[contains(@class, 'xvbhtw8') and contains(@class, 'x1lliihq')]",  # Classes de elementos da interface
                        ]
                        
                        for selector in alt_selectors:
                            try:
                                element = safe_find_element(driver, By.XPATH, selector, timeout=5)
                                log_emoji(logger, 'info', f'Login confirmado usando seletor alternativo: {selector}')
                                break
                            except Exception:
                                continue
                        else:
                            # Se nenhum seletor funcionar, verificar se há tela de verificação
                            if 'challenge' in driver.current_url or 'security' in driver.current_url:
                                raise Exception("Verificação de segurança do Instagram detectada. Login requer verificação manual.")
                            else:
                                # Por último, tirar screenshot e tentar prosseguir mesmo assim
                                capture_error_screenshot(driver, "post_login_detection", "Falha ao detectar elementos pós-login")
                                log_emoji(logger, 'warning', 'Não foi possível confirmar o login, mas tentando prosseguir')
                except Exception as e2:
                    # Se todas as alternativas falharem, relançar a exceção original com mais detalhes
                    log_emoji(logger, 'error', f'Todas as estratégias de detecção de login falharam: {str(e2)}')
                    raise Exception(f"Falha na detecção do login: {str(e1)}. Tentativas alternativas: {str(e2)}")
            
            # Verificar uso de memória após login
            mem_after = check_memory_usage()
            log_emoji(logger, 'info', f'Memória após autenticação: {mem_after:.2f} MB (delta: {mem_after - mem_before:.2f} MB)')
            
            log_emoji(logger, 'info', 'Login realizado com sucesso')
            return driver
            
        except Exception as timeout_error:
            # Extrair detalhes da exceção para diagnóstico
            error_details = str(timeout_error)
            error_tb = traceback.format_exc()
            error_class = timeout_error.__class__.__name__
            
            # Tentar extrair mais informações da página atual
            page_info = ""
            try:
                if driver.current_url:
                    page_info += f"URL atual: {driver.current_url}\n"
                if driver.title:
                    page_info += f"Título da página: {driver.title}\n"
                
                # Verificar se há alguma mensagem de erro visível na página
                error_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'error') or contains(text(), 'incorrect')]")
                if error_elements:
                    page_info += "Possíveis mensagens de erro na página:\n"
                    for elem in error_elements[:3]:  # Limitar a 3 para não poluir o log
                        page_info += f"- {elem.text}\n"
            except Exception as page_check_error:
                page_info += f"Não foi possível extrair informações da página: {str(page_check_error)}\n"
            
            # Log detalhado do erro para o arquivo de log
            log_emoji(logger, 'error', f'Erro durante o login: {error_class}: {error_details}')
            log_emoji(logger, 'error', f'Contexto da página:\n{page_info}')
            log_emoji(logger, 'error', f'Traceback completo:\n{error_tb}')
            
            # Capturar screenshot com todas as informações de contexto
            error_context = f"Tipo: {error_class}\nDetalhes: {error_details}\n\n{page_info}"
            screenshot_path = capture_error_screenshot(driver, "login_failure", error_context)
            log_emoji(logger, 'info', f'Screenshot de erro salvo como {screenshot_path}')
            
            # Verificar se o erro pode ser causado por detecção de automação ou verificação de segurança
            try:
                # Buscar elementos específicos de desafios de segurança
                security_elements = driver.find_elements(By.XPATH, 
                    "//div[contains(text(), 'challenge') or contains(text(), 'verify') or "
                    "contains(text(), 'security') or contains(text(), 'suspicious') or "
                    "contains(text(), 'unusual') or contains(text(), 'captcha') or "
                    "contains(text(), 'verificar') or contains(text(), 'segurança')]"
                )
                
                if security_elements:
                    log_emoji(logger, 'warning', 'Detectada possível verificação de segurança do Instagram')
                    security_text = "\n".join([e.text for e in security_elements[:3]])
                    log_emoji(logger, 'info', f'Textos de segurança: {security_text}')
                    
                # Verificar se estamos em uma URL específica de desafio
                if 'challenge' in driver.current_url or 'security' in driver.current_url:
                    log_emoji(logger, 'warning', f'URL de desafio de segurança detectada: {driver.current_url}')
            except Exception as sec_check_error:
                log_emoji(logger, 'debug', f'Erro ao verificar elementos de segurança: {str(sec_check_error)}')
            
            # Limpar recursos
            driver.quit()
            
            # Criar mensagem de erro amigável com dicas de solução
            error_message = f"Falha no login: {error_class}\n"
            
            # Adicionar dicas específicas com base no tipo de erro
            if "TimeoutException" in error_class:
                error_message += "\nPossíveis causas:\n"
                error_message += "- O Instagram está demorando muito para responder\n"
                error_message += "- O Instagram pode estar detectando automação\n"
                error_message += "- O Instagram está exigindo verificação de segurança\n"
                error_message += "- Credenciais incorretas\n\n"
                error_message += "Dicas:\n"
                error_message += "- Verifique usuário e senha\n"
                error_message += "- Tente fazer login manualmente primeiro para resolver verificações pendentes\n"
                error_message += "- Desative autenticação de dois fatores temporariamente\n"
                error_message += "- Se o erro persistir, considere usar um IP diferente ou aguardar 24 horas\n"
                error_message += "- Verifique se sua conta não está com restrições\n"
            elif "NoSuchElementException" in error_class:
                error_message += "\nPossíveis causas:\n"
                error_message += "- A interface do Instagram mudou\n"
                error_message += "- O Instagram apresentou página diferente do esperado\n\n"
                error_message += "Dicas:\n"
                error_message += "- Verifique se há mensagens de segurança do Instagram\n"
                error_message += "- Tente fazer login manualmente primeiro\n"
            
            # Adicionar caminho do screenshot para referência
            if screenshot_path:
                error_message += f"\nUm screenshot foi salvo para diagnóstico: {os.path.basename(screenshot_path)}"
            
            # Lançar exceção com mensagem mais informativa
            raise Exception(error_message)
            
    except Exception as e:
        log_emoji(logger, 'error', f'Erro de autenticação: {str(e)}')
        if driver:
            try:
                driver.quit()
            except:
                pass
        raise Exception(f"Erro de autenticação: {str(e)}")

# Função de adicionar usuários ao Close Friends
async def add_users_to_close_friends(driver, websocket: WebSocket):
    global stop_process
    
    try:
        # Registrar uso de memória inicial
        mem_usage_start = check_memory_usage()
        log_emoji(logger, 'info', f'Uso de memória inicial: {mem_usage_start:.2f} MB')
        
        # Definir timeout de página explícito para esta navegação
        driver.set_page_load_timeout(30)
        driver.get("https://www.instagram.com/accounts/close_friends/")
        
        # Esperar a página de Close Friends carregar completamente usando nossa função com retry
        try:
            safe_find_element(driver, By.XPATH, "//div[@data-bloks-name='ig.components.Icon']", timeout=15)
        except Exception as e:
            screenshot_path = capture_error_screenshot(driver, "close_friends_page_load_error", f"Erro: {str(e)}")
            log_emoji(logger, 'error', f'Timeout ao carregar a página de Close Friends: {str(e)}')
            await websocket.send_text(f"❌ Timeout ao carregar a página de Close Friends. Screenshot: {screenshot_path}")
            return 0
            
        # Log de início de processamento de contatos
        log_emoji(logger, 'info', 'Iniciando processamento de contatos para Close Friends')
        await websocket.send_text("🚀 Iniciando adição de contatos ao Close Friends...")

        last_height = driver.execute_script("return document.body.scrollHeight")
        total_adicionados = 0
        scroll_attempts = 0
        max_scroll_attempts = 5  # Limitar número de tentativas em caso de falha na rolagem
        batch_size = 0  # Contador para limpar a página periodicamente

        while not stop_process:
            # Tentar recuperar os ícones com nossa função com retry
            try:
                # Usar uma estratégia diferente para encontrar os ícones com base no estilo
                icons = safe_find_elements(
                    driver, 
                    By.XPATH, 
                    "//div[@data-bloks-name='ig.components.Icon' and contains(@style, 'circle__outline')]",
                    timeout=15
                )
                
                if not icons:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        log_emoji(logger, 'info', 'Não foram encontrados mais contatos após várias tentativas')
                        await websocket.send_text("✅ Processamento concluído após várias tentativas de rolagem")
                        break
                else:
                    scroll_attempts = 0  # Resetar contador se encontramos ícones
                
                # Relatar o uso de memória a cada lote
                current_mem = check_memory_usage()
                log_emoji(logger, 'info', f'Uso de memória atual: {current_mem:.2f} MB')
                
                # Processar em lotes menores para evitar sobrecarga de memória
                for index, icon in enumerate(icons[:10]):  # Limitar a 10 por vez
                    if stop_process:
                        log_emoji(logger, 'info', 'Processo interrompido pelo usuário.')
                        await websocket.send_text("Processo interrompido pelo usuário.")
                        return total_adicionados
                    
                    try:
                        # Garantir que o elemento está visível antes de clicar
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", icon)
                        log_emoji(logger, 'debug', f'Rolando para o elemento {index+1} da lista para torná-lo visível')
                        await asyncio.sleep(0.5)  # Pequena pausa para a rolagem completar
                        
                        # Obter informações do usuário se possível
                        try:
                            # Tenta encontrar o nome de usuário ou texto relacionado
                            user_details = safe_find_element(driver, By.XPATH, 
                                f"(//div[@data-bloks-name='ig.components.Icon' and contains(@style, 'circle__outline')])[{index + 1}]/ancestor::div[contains(@role, 'button')]//*[contains(@class, 'Text')]")
                            if user_details:
                                username = user_details.text
                                log_emoji(logger, 'info', f'Tentando adicionar usuário: {username}')
                        except Exception as user_info_error:
                            log_emoji(logger, 'debug', f'Não foi possível obter nome do usuário: {str(user_info_error)}')
                            username = f"usuário #{total_adicionados+1}"
                        
                        # Tentar clicar no item usando nossa função com retry
                        log_emoji(logger, 'debug', f'Localizando elemento pai para o ícone {index+1}')
                        parent_element = safe_find_element(driver, By.XPATH, 
                                            f"(//div[@data-bloks-name='ig.components.Icon' and contains(@style, 'circle__outline')])[{index + 1}]/..",
                                            timeout=5)
                        
                        log_emoji(logger, 'debug', f'Tentando clicar no elemento para {username}')
                        click_start_time = time.time()
                        click_successful = safe_click(parent_element)
                        click_time = time.time() - click_start_time
                        
                        if click_successful:
                            total_adicionados += 1
                            batch_size += 1
                            log_emoji(logger, 'info', f'✅ {username} adicionado ao Close Friends (#{total_adicionados}) em {click_time:.2f}s')
                            await websocket.send_text(f"✅ {username} adicionado! ({total_adicionados} usuários no total)")
                            
                            # Pausa dinâmica para evitar detecção como bot
                            # Varia o tempo entre 2-4 segundos
                            await asyncio.sleep(2 + (index % 3))  
                    except Exception as e:
                        log_emoji(logger, 'error', f'Erro ao adicionar usuário: {str(e)}')
                        await websocket.send_text(f"Aviso: Erro ao adicionar um usuário, continuando...")
                        continue
                
                # Periodicamente recarregar a página para evitar acumular muito DOM/memória
                if batch_size >= 50 or current_mem > 500:  # Recarregar se usar mais de 500MB
                    log_emoji(logger, 'info', f'🔄 Recarregando página para limpar recursos. Memória: {current_mem:.2f} MB após {batch_size} adições')
                    
                    # Coletar estatísticas para o log
                    batch_stats = {
                        "batch_size": batch_size,
                        "memory_usage_mb": current_mem,
                        "total_added_so_far": total_adicionados,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    log_emoji(logger, 'info', f'Estatísticas do lote: {batch_stats}')
                    
                    await websocket.send_text(f"🔄 Otimizando recursos... ({batch_size} usuários processados neste lote, total: {total_adicionados})")
                    
                    refresh_start = time.time()
                    driver.refresh()
                    refresh_time = time.time() - refresh_start
                    log_emoji(logger, 'debug', f'Tempo de atualização da página: {refresh_time:.2f}s')
                    
                    await asyncio.sleep(5)
                    batch_size = 0
                    
                    # Forçar coleta de lixo
                    mem_before_gc = current_mem
                    gc.collect()
                    current_mem = check_memory_usage()
                    log_emoji(logger, 'info', f'Memória após GC: {current_mem:.2f} MB (liberado: {mem_before_gc - current_mem:.2f} MB)')
                    continue
            
            except TimeoutException:
                # Se não encontrar mais ícones, tente rolar mais
                log_emoji(logger, 'warning', 'Timeout ao buscar ícones, tentando rolar mais')
                await websocket.send_text("Buscando mais usuários...")
            
            # Rolar para carregar mais elementos
            log_emoji(logger, 'debug', f'Rolando para carregar mais elementos. Altura atual: {last_height}')
            scroll_start = time.time()
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")  # Rolagem mais suave
            log_emoji(logger, 'debug', f'Comando de rolagem executado em {(time.time() - scroll_start):.3f}s')
            log_emoji(logger, 'info', f'Aguardando carregamento de novos elementos... ({total_adicionados} adicionados até agora)')
            await asyncio.sleep(3)  # Espera mais longa para carregar
            
            # Verificar se chegamos ao fim da página
            new_height = driver.execute_script("return document.body.scrollHeight")
            log_emoji(logger, 'debug', f'Nova altura da página: {new_height}, altura anterior: {last_height}')
            
            if new_height == last_height:
                scroll_attempts += 1
                log_emoji(logger, 'info', f'⚠️ Não há novos elementos - tentativa {scroll_attempts}/{max_scroll_attempts}')
                
                if scroll_attempts >= max_scroll_attempts:
                    log_emoji(logger, 'info', f'🏁 Fim da página atingido após {scroll_attempts} tentativas. Total de {total_adicionados} usuários adicionados.')
                    await websocket.send_text(f"✅ Todos os contatos processados! Total: {total_adicionados} usuários adicionados ao Close Friends.")
                    break
            else:
                height_diff = new_height - last_height
                last_height = new_height
                scroll_attempts = 0  # Resetar contador se a rolagem funcionou
                log_emoji(logger, 'info', f'📜 Novos elementos carregados (altura +{height_diff}px). Continuando processamento...')
        
        # Uso de memória final
        mem_usage_end = check_memory_usage()
        log_emoji(logger, 'info', f'Uso de memória final: {mem_usage_end:.2f} MB')
        log_emoji(logger, 'info', f'Variação de memória: {mem_usage_end - mem_usage_start:.2f} MB')
        
        return total_adicionados
        
    except Exception as e:
        log_emoji(logger, 'error', f'Erro durante o processamento de Close Friends: {str(e)}')
        # Capturar screenshot com detalhes do erro
        try:
            error_context = f"Erro durante processamento: {str(e)}\nTotal adicionados até o erro: {total_adicionados}"
            screenshot_path = capture_error_screenshot(driver, "close_friends_error", error_context)
            await websocket.send_text(f"💥 Erro: {str(e)}. Screenshot salvo para diagnóstico: {screenshot_path}")
        except Exception as screenshot_error:
            log_emoji(logger, 'error', f'Erro ao capturar screenshot: {str(screenshot_error)}')
            await websocket.send_text(f"💥 Erro: {str(e)}. Não foi possível salvar screenshot.")
        
        # Registrar o traceback para depuração
        error_traceback = traceback.format_exc()
        log_emoji(logger, 'error', f'Detalhes do erro:\n{error_traceback}')
        
        return total_adicionados


# Endpoint para verificar status do sistema
@app.get("/status")
async def get_system_status():
    """Endpoint para verificar o estado do sistema e uso de memória"""
    try:
        # Importar módulos necessários
        import sys
        import os
        
        # Coletar informações do sistema
        process = psutil.Process()
        mem_info = process.memory_info()
        memory_usage = mem_info.rss / (1024 * 1024)  # MB
        cpu_usage = process.cpu_percent(interval=0.5)
        system_info = {
            "status": "running",
            "memory_mb": round(memory_usage, 2),
            "cpu_percent": cpu_usage,
            "threads": len(process.threads()),
            "uptime_seconds": int(time.time() - process.create_time()),
            "process_status": process.status(),
            "python_version": sys.version,
            "global_status": "running" if not stop_process else "stopped"
        }
        
        # Forçar coleta de lixo e medir novamente
        gc.collect()
        mem_after_gc = process.memory_info().rss / (1024 * 1024)
        
        # Adicionar métricas pós-GC
        system_info["memory_after_gc_mb"] = round(mem_after_gc, 2)
        system_info["memory_freed_mb"] = round(memory_usage - mem_after_gc, 2)
        
        # Coletar métricas do GC
        gc_counts = gc.get_count()
        system_info["gc_stats"] = {
            "collections": {
                "generation0": gc_counts[0],
                "generation1": gc_counts[1],
                "generation2": gc_counts[2]
            },
            "objects": len(gc.get_objects())
        }
        
        # Listar screenshots disponíveis para debug
        screenshots_dir = os.path.join(os.getcwd(), "screenshots")
        screenshots = []
        if os.path.exists(screenshots_dir):
            screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith(".png")]
            screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(screenshots_dir, x)), reverse=True)
        system_info["screenshots"] = screenshots[:10]  # Apenas os 10 mais recentes
        
        log_emoji(logger, 'info', f'Status do sistema verificado. Memória: {memory_usage:.2f} MB')
        return system_info
    except Exception as e:
        log_emoji(logger, 'error', f'Erro ao obter status do sistema: {str(e)}')
        return {"status": "error", "error": str(e)}
        

# Endpoint para verificar a versão
@app.get("/version")
def get_version():
    return {"version": "1.0.1", "updated_at": "2025-03-02"}