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
from pydantic import BaseModel
import logging
import traceback
import gc
import psutil

# Importar Tenacity para retentativas automáticas
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

app = FastAPI()

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

import traceback
import gc

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global stop_process
    stop_process = False  
    driver = None

    await websocket.accept()
    try:
        try:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            username = data.get("username")
            password = data.get("password")
            
            if not username or not password:
                raise ValueError("Nome de usuário e senha são obrigatórios")
            
        except asyncio.TimeoutError:
            log_emoji(logger, 'error', 'Timeout ao receber credenciais')
            await websocket.send_text("Timeout ao receber credenciais. Por favor, tente novamente.")
            return
        except Exception as e:
            log_emoji(logger, 'error', f'Erro ao processar dados de entrada: {str(e)}')
            await websocket.send_text(f"Erro ao processar dados de entrada: {str(e)}")
            return

        log_emoji(logger, 'info', 'Iniciando autenticação...')
        await websocket.send_text("Iniciando autenticação...")
        
        try:
            driver = authenticate(username, password)
        except Exception as auth_error:
            log_emoji(logger, 'error', f'Falha na autenticação: {str(auth_error)}')
            await websocket.send_text(f"Falha na autenticação: {str(auth_error)}")
            return
            
        log_emoji(logger, 'info', 'Autenticação bem-sucedida!')
        await websocket.send_text("Autenticação bem-sucedida! Adicionando usuários ao Close Friends...")

        try:
            # Estabelecer um timeout global para o processo
            total_adicionados = await asyncio.wait_for(
                add_users_to_close_friends(driver, websocket),
                timeout=3600  # 1 hora de timeout máximo
            )
            log_emoji(logger, 'info', f'Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.')
            await websocket.send_text(f"Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.")
        except asyncio.TimeoutError:
            log_emoji(logger, 'error', 'O processo excedeu o tempo limite máximo (1 hora)')
            await websocket.send_text("O processo excedeu o tempo limite máximo de 1 hora. Por favor, divida o processamento em partes menores.")
        except Exception as process_error:
            log_emoji(logger, 'error', f'Erro durante o processamento: {str(process_error)}')
            await websocket.send_text(f"Erro durante o processamento: {str(process_error)}")
            # Registrar o traceback para depuração
            error_traceback = traceback.format_exc()
            log_emoji(logger, 'error', f'Detalhes do erro:\n{error_traceback}')
    except Exception as e:
        log_emoji(logger, 'error', f'Erro global: {str(e)}')
        await websocket.send_text(f"Erro global: {str(e)}")
    finally:
        # Garantir que o driver é fechado corretamente
        if driver:
            try:
                driver.quit()
            except:
                pass
            driver = None
        
        # Forçar coleta de lixo para liberar memória
        gc.collect()
        
        # Fechar a conexão websocket
        try:
            await websocket.close()
        except:
            pass

@app.post("/stop")
async def stop_process_api():
    global stop_process
    stop_process = True  

    
    return {"message": "Processo interrompido!"}

def authenticate(username: str, password: str):
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

    # Tentar criar o driver com tentativas em caso de falha
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            driver = uc.Chrome(options=options)
            break
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f"Falha ao iniciar o navegador após {max_retries} tentativas: {str(e)}")
            time.sleep(2)  # Espera antes de tentar novamente

    try:
        # Definir timeout de página explícito
        driver.set_page_load_timeout(30)
        driver.get("https://www.instagram.com/")
        
        # Esperar explicitamente pelos elementos
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        
        wait = WebDriverWait(driver, 15)
        
        try:
            username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            
            username_input.clear()
            username_input.send_keys(username)
            password_input.clear()
            password_input.send_keys(password)
            password_input.send_keys(Keys.RETURN)
            
            # Esperar explicitamente pelo login bem-sucedido (verificando se algum elemento pós-login está presente)
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog' or @role='main']")))
            
            return driver
        except TimeoutException:
            driver.save_screenshot("login_timeout.png")
            driver.quit()
            raise Exception("Timeout ao esperar pelos elementos de login do Instagram")
            
    except Exception as e:
        if driver:
            driver.quit()
        raise Exception(f"Erro de autenticação: {str(e)}")

# Função de adicionar usuários ao Close Friends
async def add_users_to_close_friends(driver, websocket: WebSocket):
    global stop_process
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
    
    # Configurando WebDriverWait
    wait = WebDriverWait(driver, 15)
    
    try:
        # Definir timeout de página explícito para esta navegação
        driver.set_page_load_timeout(30)
        driver.get("https://www.instagram.com/accounts/close_friends/")
        
        # Esperar a página de Close Friends carregar completamente
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")))
        except TimeoutException:
            driver.save_screenshot("close_friends_page_load_error.png")
            log_emoji(logger, 'error', 'Timeout ao carregar a página de Close Friends')
            await websocket.send_text("❌ Timeout ao carregar a página de Close Friends")
            return 0
            
        # Log de início de processamento de contatos
        log_emoji(logger, 'info', 'Iniciando processamento de contatos para Close Friends')
        await websocket.send_text("🚀 Iniciando adição de contatos ao Close Friends...")

        last_height = driver.execute_script("return document.body.scrollHeight")
        total_adicionados = 0
        scroll_attempts = 0
        max_scroll_attempts = 5  # Limitar número de tentativas em caso de falha na rolagem
        batch_size = 0  # Contador para limpar a página periodicamente

        # Implementação de retry para elementos que falham na primeira tentativa
        def click_with_retry(element, max_retries=3):
            for retry in range(max_retries):
                try:
                    element.click()
                    return True
                except (StaleElementReferenceException, NoSuchElementException) as e:
                    if retry == max_retries - 1:
                        raise e
                    await asyncio.sleep(0.5)
            return False

        while not stop_process:
            # Tentar recuperar os ícones com espera explícita
            try:
                # Usar uma estratégia diferente para encontrar os ícones com base no estilo
                # Esta abordagem é mais robusta do que procurar todos os ícones e depois filtrar
                icons = wait.until(EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@data-bloks-name='ig.components.Icon' and contains(@style, 'circle__outline')]")))
                
                if not icons:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        log_emoji(logger, 'info', 'Não foram encontrados mais contatos após várias tentativas')
                        await websocket.send_text("✅ Processamento concluído após várias tentativas de rolagem")
                        break
                else:
                    scroll_attempts = 0  # Resetar contador se encontramos ícones
                
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
                        
                        # Tentar clicar no item com retry
                        parent_element = icon.find_element(By.XPATH, "..")
                        if click_with_retry(parent_element):
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
                if batch_size >= 50:
                    log_emoji(logger, 'info', 'Recarregando página para limpar recursos')
                    await websocket.send_text("Recarregando página para otimizar recursos...")
                    driver.refresh()
                    await asyncio.sleep(5)
                    batch_size = 0
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
        
        return total_adicionados
        
    except Exception as e:
        log_emoji(logger, 'error', f'Erro durante o processamento de Close Friends: {str(e)}')
        await websocket.send_text(f"Erro: {str(e)}")
        # Tira um screenshot para diagnóstico
        try:
            driver.save_screenshot("close_friends_error.png")
        except:
            pass
        return total_adicionados