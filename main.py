from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
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

stop_process = False 

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
            
            if not username or not password:
                raise ValueError("Nome de usuário e senha são obrigatórios")
            
            log_emoji(logger, 'info', f'Credenciais recebidas para o usuário: {username}')
            
        except asyncio.TimeoutError:
            log_emoji(logger, 'error', 'Timeout ao receber credenciais')
            await websocket.send_text("⚠️ Timeout ao receber credenciais. Por favor, tente novamente.")
            return
        except Exception as e:
            log_emoji(logger, 'error', f'Erro ao processar dados de entrada: {str(e)}')
            await websocket.send_text(f"❌ Erro ao processar dados de entrada: {str(e)}")
            return

        # Monitorar memória antes da autenticação
        pre_auth_memory = check_memory_usage()
        log_emoji(logger, 'info', f'Memória antes da autenticação: {pre_auth_memory:.2f} MB')
        
        log_emoji(logger, 'info', 'Iniciando autenticação...')
        await websocket.send_text("🔑 Iniciando autenticação...")
        
        try:
            driver = authenticate(username, password)
        except Exception as auth_error:
            log_emoji(logger, 'error', f'Falha na autenticação: {str(auth_error)}')
            await websocket.send_text(f"❌ Falha na autenticação: {str(auth_error)}")
            return
        
        # Monitorar memória após autenticação
        post_auth_memory = check_memory_usage()
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
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled") 
    # Adicionar mais memória para o Chrome
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-notifications")
    options.add_argument("--memory-pressure-off")
    options.add_argument("--process-per-site")
    options.add_argument("--single-process")
    
    # Parâmetros para evitar detecção de automação
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-popup-blocking")
    
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
            
            # Limpar e preencher os campos
            log_emoji(logger, 'info', 'Preenchendo credenciais')
            username_input.clear()
            username_input.send_keys(username)
            password_input.clear()
            password_input.send_keys(password)
            
            # Enviar o formulário
            log_emoji(logger, 'info', 'Enviando formulário de login')
            password_input.send_keys(Keys.RETURN)
            
            # Esperar o login com nossa função com retry
            log_emoji(logger, 'info', 'Aguardando confirmação de login')
            safe_find_element(driver, By.XPATH, "//div[@role='dialog' or @role='main']", timeout=20)
            
            # Verificar uso de memória após login
            mem_after = check_memory_usage()
            log_emoji(logger, 'info', f'Memória após autenticação: {mem_after:.2f} MB (delta: {mem_after - mem_before:.2f} MB)')
            
            log_emoji(logger, 'info', 'Login realizado com sucesso')
            return driver
            
        except Exception as timeout_error:
            log_emoji(logger, 'error', f'Erro durante o login: {str(timeout_error)}')
            screenshot_path = capture_error_screenshot(driver, "login_failure", f"Erro: {str(timeout_error)}")
            log_emoji(logger, 'info', f'Screenshot de erro salvo como {screenshot_path}')
            driver.quit()
            raise Exception(f"Falha no login: {str(timeout_error)}")
            
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
                        await asyncio.sleep(0.5)  # Pequena pausa para a rolagem completar
                        
                        # Tentar clicar no item usando nossa função com retry
                        parent_element = safe_find_element(driver, By.XPATH, 
                                            f"(//div[@data-bloks-name='ig.components.Icon' and contains(@style, 'circle__outline')])[{index + 1}]/..",
                                            timeout=5)
                        
                        if safe_click(parent_element):
                            total_adicionados += 1
                            batch_size += 1
                            log_emoji(logger, 'info', f'{total_adicionados} usuários adicionados ao Close Friends')
                            await websocket.send_text(f"{total_adicionados} usuários adicionados...")
                            
                            # Pausa dinâmica para evitar detecção como bot
                            # Varia o tempo entre 2-4 segundos
                            await asyncio.sleep(2 + (index % 3))  
                    except Exception as e:
                        log_emoji(logger, 'error', f'Erro ao adicionar usuário: {str(e)}')
                        await websocket.send_text(f"Aviso: Erro ao adicionar um usuário, continuando...")
                        continue
                
                # Periodicamente recarregar a página para evitar acumular muito DOM/memória
                if batch_size >= 50 or current_mem > 500:  # Recarregar se usar mais de 500MB
                    log_emoji(logger, 'info', f'Recarregando página para limpar recursos. Memória: {current_mem:.2f} MB')
                    await websocket.send_text("Recarregando página para otimizar recursos...")
                    driver.refresh()
                    await asyncio.sleep(5)
                    batch_size = 0
                    # Forçar coleta de lixo
                    gc.collect()
                    continue
            
            except TimeoutException:
                # Se não encontrar mais ícones, tente rolar mais
                log_emoji(logger, 'warning', 'Timeout ao buscar ícones, tentando rolar mais')
                await websocket.send_text("Buscando mais usuários...")
            
            # Rolar para carregar mais elementos
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")  # Rolagem mais suave
            await asyncio.sleep(3)  # Espera mais longa para carregar
            
            # Verificar se chegamos ao fim da página
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
                if scroll_attempts >= max_scroll_attempts:
                    log_emoji(logger, 'info', 'Fim da página atingido, todos os contatos processados')
                    await websocket.send_text("✅ Todos os contatos processados")
                    break
            else:
                last_height = new_height
                scroll_attempts = 0  # Resetar contador se a rolagem funcionou
        
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