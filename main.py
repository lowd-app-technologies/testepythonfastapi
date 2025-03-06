from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pydantic import BaseModel
import logging

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
    
    emoji = emoji_map.get(level.lower(), emoji)
    
    emoji_message = f"{emoji} {message}"
    
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

        log_emoji(logger, 'info', 'Iniciando autenticação...')
        await websocket.send_text("Iniciando autenticação...")
        driver = authenticate(username, password)
        log_emoji(logger, 'info', "Autenticação bem-sucedida! Adicionando usuários ao Close Friends...")
        await websocket.send_text("Autenticação bem-sucedida! Adicionando usuários ao Close Friends...")

        total_adicionados = await add_users_to_close_friends(driver, websocket)
        driver.quit()

        log_emoji(logger, 'info', f'Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.')
        await websocket.send_text(f"Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.")
    except Exception as e:
        log_emoji(logger, 'error', f'Erro: {str(e)}')
        await websocket.send_text(f"Erro: {str(e)}")
    finally:
        await websocket.close()

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
    global stop_process
    driver.get("https://www.instagram.com/accounts/close_friends/")
    await asyncio.sleep(5)  

    total_adicionados = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0  

    while not stop_process:
        
        icons = driver.find_elements(By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")
        current_followers = len(icons)  

        for icon in icons:
            if stop_process:
                log_emoji(logger, 'info', 'Processo interrompido pelo usuário.')
                await websocket.send_text("Processo interrompido pelo usuário.")
                return total_adicionados

            if 'circle__outline' in icon.get_attribute('style'):
                driver.execute_script("arguments[0].scrollIntoView();", icon)
                await asyncio.sleep(1)
                try:
                    add_button = icon.find_element(By.XPATH, "..")
                    add_button.click()
                    total_adicionados += 1
                    await websocket.send_text(f"{total_adicionados} usuários adicionados...")
                    await asyncio.sleep(3)  
                except Exception as e:
                    log_emoji(logger, 'error', f"Erro ao clicar: {str(e)}")
                    await websocket.send_text(f"Erro ao clicar: {str(e)}")

        
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        await asyncio.sleep(2)  

        new_height = driver.execute_script("return document.body.scrollHeight")
        
        
        if new_height == last_height:
            scroll_attempts += 1
            if scroll_attempts >= 2:  
                driver.refresh()
                log_emoji(logger, 'info', 'Recarregando a página...')  
                await asyncio.sleep(5)  
                scroll_attempts = 0  
        else:
            scroll_attempts = 0  

        if scroll_attempts == 0 and len(driver.find_elements(By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")) == current_followers:
            log_emoji(logger, 'info', 'Todos os usuários foram adicionados com sucesso.')
            await websocket.send_text(f"Todos os usuários foram adicionados com sucesso.")
            break

        last_height = new_height

    return total_adicionados
