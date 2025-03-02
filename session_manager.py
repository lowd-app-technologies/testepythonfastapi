import os
import json
import pickle
import logging
from datetime import datetime
import asyncio
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi import WebSocket

# Configurar diretório de sessões
SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)

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
    """
    emoji_map = {
        'info': '🌐',
        'warning': '⚠️',
        'error': '💥',
        'critical': '🚨',
        'debug': '🔍'
    }
    
    emoji = emoji_map.get(level, emoji)
    log_message = f"{emoji} {message}"
    
    if level == 'info':
        logger.info(log_message)
    elif level == 'warning':
        logger.warning(log_message)
    elif level == 'error':
        logger.error(log_message)
    elif level == 'critical':
        logger.critical(log_message)
    elif level == 'debug':
        logger.debug(log_message)

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
            options = uc.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument("--remote-debugging-port=9222")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            driver = uc.Chrome(options=options)
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
                    (By.XPATH, "//span[contains(@class, 'coreSpriteProfilePic')]/.. | //span[contains(@class, 'xp7jhwk')]/.. | //div[contains(@class, '_aarf')]/.. | //div[contains(@data-bloks-name, 'ig.components.ProfilePicture')]/..")
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
