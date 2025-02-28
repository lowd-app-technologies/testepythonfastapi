from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import asyncio
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi.middleware.cors import CORSMiddleware
import random

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

    icons = driver.find_elements(By.XPATH, "//div[@data-bloks-name='ig.components.Icon']")
    total_adicionados = 0

    for index, icon in enumerate(icons):
        if 'circle__outline' in icon.get_attribute('style'):
            add_button = icon.find_element(By.XPATH, "..")
            
            # Verificar o estilo do botão antes de clicar
            button_style = add_button.get_attribute('style')
            if 'pointer-events: none;' in button_style:
                print("O botão está desabilitado.")
                continue  # Pula esse botão se estiver desabilitado
            
            # Rolando até o botão para garantir que está visível
            driver.execute_script("arguments[0].scrollIntoView();", add_button)
            time.sleep(1)  # Pequeno delay para garantir a rolagem
            
            try:
                # Aumentando o tempo de espera
                wait = WebDriverWait(driver, 20)
                add_button = wait.until(EC.element_to_be_clickable((By.XPATH, "..")))
                driver.execute_script("arguments[0].click();", add_button)
                total_adicionados += 1
                time.sleep(3)
            except Exception as e:
                await websocket.send_text(f"Erro ao clicar no botão: {str(e)}")
                print(f"Erro ao clicar no botão: {str(e)}")
                raise

    # Implementando processamento em lote
    followers_list = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Adicionar ao Close Friends"]')
    if not followers_list:
        print("Nenhum seguidor encontrado para adicionar ao Close Friends.")
        return 0

    total_adicionados = processar_seguidores_otimizado(driver, followers_list, modo='rapido')
    
    return total_adicionados

def processar_seguidores_otimizado(driver, followers_list, modo='padrao'):
    """
    Processa seguidores em um cronograma otimizado.
    
    Modos:
    - 'padrao': 100 seguidores a cada 5 minutos
    - 'rapido': 150 seguidores a cada 5 minutos
    - 'turno': Processamento em turnos de 4 horas
    """
    total_adicionados = 0
    total_seguidores = len(followers_list)
    
    # Configurações de processamento
    if modo == 'padrao':
        seguidores_por_lote = 100
        intervalo_lote = 300  # 5 minutos
    elif modo == 'rapido':
        seguidores_por_lote = 150
        intervalo_lote = 300  # 5 minutos
    elif modo == 'turno':
        seguidores_por_lote = 100
        intervalo_lote = 14400  # 4 horas
    else:
        raise ValueError("Modo inválido. Escolha entre 'padrao', 'rapido' ou 'turno'.")
    
    print(f"Iniciando processamento no modo {modo}")
    print(f"Total de seguidores: {total_seguidores}")
    print(f"Seguidores por lote: {seguidores_por_lote}")
    print(f"Intervalo entre lotes: {intervalo_lote/60} minutos")
    
    try:
        for i in range(0, total_seguidores, seguidores_por_lote):
            batch = followers_list[i:i+seguidores_por_lote]
            print(f"\nProcessando lote {i//seguidores_por_lote + 1}")
            print(f"Processando {len(batch)} seguidores...")
            
            for follower in batch:
                try:
                    add_button = driver.find_element_by_css_selector('button[aria-label="Adicionar ao Close Friends"]')
                    add_button.click()
                    total_adicionados += 1
                    
                    # Atraso humano entre ações
                    time.sleep(random.randint(2, 5))
                except Exception as e:
                    print(f"Erro ao adicionar seguidor: {str(e)}")
            
            print(f"Lote concluído. Total adicionados: {total_adicionados}")
            
            # Aguardar entre lotes
            if i + seguidores_por_lote < total_seguidores:
                print(f"Aguardando {intervalo_lote/60} minutos antes do próximo lote...")
                time.sleep(intervalo_lote)
    
    except Exception as e:
        print(f"Erro no processamento: {str(e)}")
    
    finally:
        print(f"\nProcessamento concluído.")
        print(f"Total de seguidores adicionados: {total_adicionados}")
        print(f"Tempo estimado: {(total_seguidores/seguidores_por_lote * intervalo_lote)/3600:.2f} horas")
    
    return total_adicionados
