from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from celery import Celery
import asyncio
import time
import os

# Configuração do Celery
celery_app = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_BACKEND", "redis://localhost:6379/0")
)

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

@app.get("/health")
async def health_check():
    return JSONResponse(status_code=200, content={"message": "Server is up and running"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        username = data["username"]
        password = data["password"]
        
        await websocket.send_text("Iniciando autenticação...")
        print("Iniciando autenticação...")
        
        task = authenticate.delay(username, password)  # Executa via Celery
        await websocket.send_text(f"Tarefa iniciada. ID: {task.id}")
    
    except Exception as e:
        await websocket.send_text(f"Erro: {str(e)}")
    finally:
        await websocket.close()

@celery_app.task()
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
        
        time.sleep(5)
        print(f"Usuário {username} autenticado!")
    
    except Exception as e:
        print(f"Erro de autenticação: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
