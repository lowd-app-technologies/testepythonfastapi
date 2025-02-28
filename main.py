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
import logging
import sys
import traceback
from selenium.common.exceptions import ElementClickInterceptedException, ElementNotInteractableException

# Configuração do logging para stdout
def configurar_logging():
    # Configurar logger
    logger = logging.getLogger('ProcessamentoSeguidores')
    logger.setLevel(logging.INFO)
    
    # Configurar handler para stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    
    # Formato do log para stdout
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    stdout_handler.setFormatter(formatter)
    
    # Limpar handlers anteriores para evitar duplicação
    logger.handlers.clear()
    
    # Adicionar handler ao logger
    logger.addHandler(stdout_handler)
    
    return logger

# Configurar logger global
logger = configurar_logging()

# Decorator para logging de erros
def log_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Erro em {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    return wrapper

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

def adicionar_seguidor_close_friends(driver, follower, max_tentativas=3):
    """
    Tenta adicionar seguidor ao Close Friends com múltiplas estratégias
    """
    for tentativa in range(max_tentativas):
        try:
            # Localizar botão com espera explícita
            add_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Adicionar ao Close Friends"]'))
            )
            
            # Verificar se o botão está habilitado
            if not add_button.is_enabled():
                logger.warning(f" 🚫 Botão desabilitado na tentativa {tentativa + 1}")
                
                # Tentar rolar até o elemento
                driver.execute_script("arguments[0].scrollIntoView(true);", add_button)
                time.sleep(2)
                
                # Verificar novamente
                if not add_button.is_enabled():
                    logger.warning(f" ⏳ Aguardando botão habilitar...")
                    time.sleep(random.randint(3, 7))
                    continue
            
            # Clicar no botão
            add_button.click()
            logger.info(f" ✅ Seguidor adicionado com sucesso na tentativa {tentativa + 1}")
            return True
        
        except (ElementClickInterceptedException, ElementNotInteractableException) as e:
            logger.warning(f" 🔄 Erro ao clicar: {str(e)}. Tentativa {tentativa + 1}")
            time.sleep(random.randint(2, 5))
        
        except Exception as e:
            logger.error(f" ❌ Erro inesperado: {str(e)}")
            break
    
    logger.error(f" 💥 Falha ao adicionar seguidor após {max_tentativas} tentativas")
    return False

@log_error
def processar_seguidores_otimizado(driver, followers_list, modo='padrao'):
    """
    Processa seguidores em um cronograma otimizado com tratamento de erros
    """
    logger.info(f" 🚀 Iniciando processamento de seguidores - Modo: {modo}")
    logger.info(f" 📊 Total de seguidores: {len(followers_list)}")
    
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
        logger.error(f" ❌ Modo inválido: {modo}")
        raise ValueError("Modo inválido. Escolha entre 'padrao', 'rapido' ou 'turno'.")
    
    logger.info(f" ⚙️ Configurações: {seguidores_por_lote} seguidores por lote, intervalo de {intervalo_lote/60} minutos")
    
    try:
        for i in range(0, total_seguidores, seguidores_por_lote):
            batch = followers_list[i:i+seguidores_por_lote]
            logger.info(f" 🔄 Processando lote {i//seguidores_por_lote + 1}: {len(batch)} seguidores")
            
            for follower in batch:
                sucesso = adicionar_seguidor_close_friends(driver, follower)
                if sucesso:
                    total_adicionados += 1
                    time.sleep(random.randint(2, 5))
            
            # Aguardar entre lotes
            if i + seguidores_por_lote < total_seguidores:
                logger.info(f" ⏰ Aguardando {intervalo_lote/60} minutos antes do próximo lote")
                time.sleep(intervalo_lote)
        
        # Log de conclusão
        logger.info(f" 🏁 Processamento concluído. Total de seguidores adicionados: {total_adicionados}")
        logger.info(f" ⏱️ Tempo estimado de processamento: {(total_seguidores/seguidores_por_lote * intervalo_lote)/3600:.2f} horas")
        
        return total_adicionados
    
    except Exception as e:
        logger.error(f" 💥 Erro crítico no processamento: {str(e)}")
        raise
