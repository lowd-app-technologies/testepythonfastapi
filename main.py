from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import asyncio
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from fastapi.middleware.cors import CORSMiddleware

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        username = data["username"]
        password = data["password"]
        
        await websocket.send_text("Iniciando autenticação...")
        driver = authenticate(username, password)
        await websocket.send_text("Autenticação bem-sucedida! Adicionando usuários ao Close Friends...")
        
        total_adicionados = await add_users_to_close_friends(driver, websocket)
        driver.quit()
        
        await websocket.send_text(f"Processo concluído! {total_adicionados} usuários adicionados ao Close Friends.")
    except Exception as e:
        await websocket.send_text(f"Erro: {str(e)}")
    finally:
        await websocket.close()

# Função de autenticação
def authenticate(username: str, password: str):
    options = uc.ChromeOptions()
    options.add_argument("--headless")  
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")  
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Evita detecção pelo Instagram

    driver = uc.Chrome(options=options)  # Usando undetected_chromedriver

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

# Função de adicionar usuários ao Close Friends
async def add_users_to_close_friends(driver, websocket: WebSocket):
    driver.get("https://www.instagram.com/accounts/close_friends/")
    time.sleep(5)

    last_height = driver.execute_script("return document.body.scrollHeight")
    total_adicionados = 0

    while True:
        icons = driver.find_elements(By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")
        
        for index, icon in enumerate(icons):
            if 'circle__outline' in icon.get_attribute('style'):
                driver.execute_script("arguments[0].scrollIntoView();", icon)  # Faz scroll até o ícone
                time.sleep(1)  # Aguarde para evitar erro de carregamento
                try:
                    add_button = icon.find_element(By.XPATH, "..")
                    add_button.click()
                    total_adicionados += 1
                    await websocket.send_text(f"{total_adicionados} usuários adicionados...")
                    time.sleep(3)  # Delay entre adições
                except Exception as e:
                    await websocket.send_text(f"Erro ao clicar: {str(e)}")
        
        # Scroll para baixo
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(2)  # Aguarde o carregamento da página

        # Verifica se carregou mais elementos
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # Sai do loop se não houver mais elementos para carregar
        last_height = new_height

    return total_adicionados
