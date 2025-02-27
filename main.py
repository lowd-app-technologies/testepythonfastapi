from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import auth

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

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth.router)


def authenticate(credentials: Credentials):
    """ Autentica no Instagram via Selenium """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Novo modo headless mais estável
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")  # Previne crash por falta de memória

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.get("https://www.instagram.com/")
        wait = WebDriverWait(driver, 10)

        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))

        username_input.send_keys(credentials.username)
        password_input.send_keys(credentials.password)
        password_input.send_keys(Keys.RETURN)

        wait.until(EC.url_contains("https://www.instagram.com/"))

        return driver  

    except Exception as e:
        driver.quit()
        raise Exception(f"Erro de autenticação: {str(e)}")


def add_users_to_close_friends(driver):
    """ Adiciona seguidores aos Close Friends """
    driver.get("https://www.instagram.com/accounts/close_friends/")
    wait = WebDriverWait(driver, 10)

    try:
        icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")))
        total_adicionados = 0

        for icon in icons:
            if 'circle__outline' in icon.get_attribute('style'):
                add_button = icon.find_element(By.XPATH, "..")
                add_button.click()
                total_adicionados += 1
                asyncio.sleep(30)  # Delay para evitar bloqueios da conta

        return total_adicionados

    except Exception as e:
        raise Exception(f"Erro ao adicionar usuários: {str(e)}")


@app.post("/run_selenium/")
async def run_selenium(credentials: Credentials):
    try:
        driver = authenticate(credentials)

        message = "Autenticação bem-sucedida! Iniciando a adição de usuários ao Close Friends..."
        
        total_adicionados = add_users_to_close_friends(driver)

        driver.quit()

        return {
            "message": message,
            "usuarios_adicionados": total_adicionados
        }

    except Exception as e:
        return {"error": str(e)}
