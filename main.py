from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pydantic import BaseModel
import logging
from datetime import datetime

# Importar gerenciador de sessões
from session_manager import check_saved_session, save_session, update_session_metadata, log_emoji

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
    use_saved_session: bool = True  # Por padrão, tenta usar sessão salva

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global stop_process
    stop_process = False  

    await websocket.accept()

    try:
        data = await websocket.receive_json()
        username = data["username"]
        password = data["password"]
        use_saved_session = data.get("use_saved_session", True)

        driver = None
        session_valid = False
        
        # Verificar se existe sessão salva e se devemos usá-la
        if use_saved_session:
            log_emoji(logger, 'info', f'Verificando sessão salva para {username[:3]}***')
            session_valid, driver = await check_saved_session(username, websocket)
        
        # Se não tivermos uma sessão válida, realizar autenticação normal
        if not session_valid:
            log_emoji(logger, 'info', 'Iniciando autenticação...')
            await websocket.send_text("Iniciando autenticação...")
            driver = authenticate(username, password)
            log_emoji(logger, 'info', 'Autenticação bem-sucedida!')
            await websocket.send_text("Autenticação bem-sucedida!")
            
            # Salvar a sessão após login bem-sucedido
            save_session(driver, username)
            await websocket.send_text("Sessão salva para uso futuro!")
        
        log_emoji(logger, 'info', 'Iniciando adição de usuários ao Close Friends...')   
        await websocket.send_text("Adicionando usuários ao Close Friends...")
        total_adicionados = await add_users_to_close_friends(driver, websocket)
        driver.quit()

        log_emoji(logger, 'info', f'Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.')
        await websocket.send_text(f"Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.")
    except Exception as e:
        log_emoji(logger, 'error', f'Erro: {str(e)}')
        await websocket.send_text(f"Erro: {str(e)}")
        
        # Atualizar status em caso de erro
        process_status["em_progresso"] = False
        process_status["erro"] = str(e)
        process_status["ultima_atualizacao"] = datetime.now().isoformat()
        
        if 'driver' in locals() and driver:
            try:
                driver.quit()
            except:
                pass
    finally:
        await websocket.close()

@app.post("/stop")
async def stop_process_api():
    global stop_process
    stop_process = True  
    return {"message": "Processo interrompido!"}

# Variável para armazenar status atual do processo
process_status = {
    "total_adicionados": 0,
    "em_progresso": False,
    "ultima_atualizacao": None,
    "erro": None
}

@app.get("/status")
async def get_status():
    global process_status
    return process_status

def authenticate(username: str, password: str):
    options = uc.ChromeOptions()
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled") 

    driver = uc.Chrome(options=options)  

    try:
        driver.get("https://www.instagram.com/")
        time.sleep(3)

        username_input = driver.find_element(By.NAME, "username")
        password_input = driver.find_element(By.NAME, "password")

        username_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)

        time.sleep(10)
        return driver
    except Exception as e:
        driver.quit()
        raise Exception(f"Erro de autenticação: {str(e)}")

async def add_users_to_close_friends(driver, websocket: WebSocket):
    global stop_process, process_status
    
    # Atualizar status do processo
    process_status["em_progresso"] = True
    process_status["total_adicionados"] = 0
    process_status["ultima_atualizacao"] = datetime.now().isoformat()
    process_status["erro"] = None
    driver.get("https://www.instagram.com/accounts/close_friends/")
    await asyncio.sleep(5)  

    # Log de início de processamento de contatos
    log_emoji(logger, 'info', 'Iniciando processamento de contatos para Close Friends')
    await websocket.send_text("🚀 Iniciando adição de contatos ao Close Friends...")

    last_height = driver.execute_script("return document.body.scrollHeight")
    total_adicionados = 0
    same_height_count = 0  # Contador para verificar se a altura está realmente estável
    max_retries = 3  # Número máximo de tentativas antes de desistir

    while not stop_process:  
        # Buscar os ícones a cada iteração para evitar elementos stale
        icons = driver.find_elements(By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")
        log_emoji(logger, 'info', f'Encontrados {len(icons)} ícones para processar')
        
        added_in_this_batch = 0  # Contador para esta rodada
        
        for index, icon in enumerate(icons):
            if stop_process:
                log_emoji(logger, 'info', 'Processo interrompido pelo usuário.')
                await websocket.send_text("Processo interrompido pelo usuário.")
                return total_adicionados  

            try:
                # Verificar se o ícone é um círculo não preenchido (usuário não adicionado)
                if 'circle__outline' in icon.get_attribute('style'):
                    # Rolar para o elemento para garantir que está visível
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", icon)
                    await asyncio.sleep(1)  
                    
                    try:
                        # Encontrar e clicar no botão de adição
                        add_button = icon.find_element(By.XPATH, "..")
                        add_button.click()
                        total_adicionados += 1
                        added_in_this_batch += 1
                        
                        # Atualizar status
                        process_status["total_adicionados"] = total_adicionados
                        process_status["ultima_atualizacao"] = datetime.now().isoformat()
                        
                        log_emoji(logger, 'info', f'{total_adicionados} usuários adicionados ao Close Friends')
                        await websocket.send_text(f"{total_adicionados} usuários adicionados...")
                        
                        # Pausa para evitar limites de taxa
                        await asyncio.sleep(3)  
                        
                        # A cada 50 usuários, fazer uma pausa maior para evitar limites
                        if total_adicionados % 50 == 0:
                            log_emoji(logger, 'info', f'Pausa após adicionar {total_adicionados} usuários')
                            await websocket.send_text(f"Pausa para evitar limites... ({total_adicionados} adicionados)")
                            await asyncio.sleep(10)  # Pausa maior a cada 50 usuários
                            
                    except Exception as e:
                        log_emoji(logger, 'error', f'Erro ao adicionar usuário: {str(e)}')
                        await websocket.send_text(f"Erro ao adicionar usuário: {str(e)}")
            except Exception as stale_error:
                # Tratar erro de elemento stale
                log_emoji(logger, 'warning', f'Elemento stale, continuando: {str(stale_error)}')
                continue

        # Rolar para carregar mais elementos
        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")  # Rolagem mais suave
        await asyncio.sleep(3)  # Aumentar pausa para carregar novos elementos
        
        # Verificar se processamos algum elemento nesta rodada
        if added_in_this_batch == 0:
            log_emoji(logger, 'info', 'Nenhum usuário adicionado nesta rodada')

        # Verificar se a altura mudou
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            same_height_count += 1
            log_emoji(logger, 'info', f'Altura estável: {same_height_count}/{max_retries}')
            
            # Se a altura não mudou por várias iterações consecutivas, considerar terminado
            if same_height_count >= max_retries:
                log_emoji(logger, 'info', 'Todos os contatos processados (altura estável por múltiplas rodadas)')
                await websocket.send_text("✅ Todos os contatos processados")
                break
                
            # Tentar uma rolagem diferente antes de desistir
            if same_height_count == 2:
                log_emoji(logger, 'info', 'Tentando rolagem alternativa...')
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        else:
            # Resetar o contador se a altura mudou
            same_height_count = 0
            last_height = new_height

    # Atualizar status final
    process_status["em_progresso"] = False
    process_status["ultima_atualizacao"] = datetime.now().isoformat()
    
    return total_adicionados