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
import os
from selenium.webdriver.common.action_chains import ActionChains

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

def diagnosticar_elemento(driver, elemento):
    """
    Diagnóstico detalhado do estado do elemento
    """
    try:
        # Capturar informações do elemento
        logger.info(f" 🔍 Diagnóstico de Elemento:")
        logger.info(f" 📍 Localização: {elemento.location}")
        logger.info(f" 📏 Tamanho: {elemento.size}")
        logger.info(f" 🟢 Visível: {elemento.is_displayed()}")
        logger.info(f" 🔘 Habilitado: {elemento.is_enabled()}")
        
        # Tentar obter atributos
        logger.info(f" 📝 Classe: {elemento.get_attribute('class')}")
        logger.info(f" 🏷️ Aria-disabled: {elemento.get_attribute('aria-disabled')}")
        
        # Screenshot de diagnóstico
        screenshot_dir = os.path.join(os.getcwd(), 'diagnostico_screenshots')
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f'elemento_diagnostico_{int(time.time())}.png')
        driver.save_screenshot(screenshot_path)
        logger.info(f" 📸 Screenshot salva em: {screenshot_path}")
    
    except Exception as e:
        logger.error(f" ❌ Erro no diagnóstico: {str(e)}")

def adicionar_seguidor_close_friends(driver, follower, max_tentativas=5):
    """
    Tenta adicionar seguidor ao Close Friends com estratégias específicas para Instagram
    """
    # XPath fornecido pelo usuário
    instagram_close_friends_xpath = '/html/body/div[1]/div/div/div[2]/div/div/div[1]/div[1]/div[1]/section/main/div/div[3]/div/div[2]/div/div/div[1]/div/div/div/div[2]/div[2]/div/div[2]/div/div[1]/div/div[2]'
    
    for tentativa in range(max_tentativas):
        try:
            logger.info(f" 🔄 Tentativa {tentativa + 1} de adicionar seguidor")
            
            # Estratégias de localização
            try:
                # Tentar localizar pelo XPath exato
                add_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, instagram_close_friends_xpath))
                )
            except Exception as xpath_error:
                logger.warning(f" ❗ Erro no XPath exato: {str(xpath_error)}")
                
                # Estratégias alternativas
                try:
                    # Tentar XPath parcial
                    add_button = driver.find_element(By.XPATH, '//div[contains(@class, "Close Friends")]')
                except:
                    try:
                        # Tentar seletor CSS
                        add_button = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Adicionar ao Close Friends"]')
                    except Exception as selector_error:
                        logger.error(f" 🚫 Falha em localizar o botão: {str(selector_error)}")
                        raise
            
            # Diagnóstico do elemento
            try:
                logger.info(f" 🔍 Detalhes do Elemento:")
                logger.info(f" 📍 Localização: {add_button.location}")
                logger.info(f" 📏 Tamanho: {add_button.size}")
                logger.info(f" 🟢 Visível: {add_button.is_displayed()}")
                logger.info(f" 🔘 Habilitado: {add_button.is_enabled()}")
            except Exception as diag_error:
                logger.warning(f" ❗ Erro no diagnóstico: {str(diag_error)}")
            
            # Estratégias de interação
            interaction_methods = [
                lambda: add_button.click(),  # Método padrão
                lambda: driver.execute_script("arguments[0].click();", add_button),  # JavaScript
                lambda: ActionChains(driver).move_to_element(add_button).click().perform(),  # Action Chains
                lambda: add_button.send_keys(Keys.ENTER)  # Enviar tecla Enter
            ]
            
            # Tentar métodos de interação
            for method in interaction_methods:
                try:
                    method()
                    logger.info(f" ✅ Seguidor adicionado com sucesso na tentativa {tentativa + 1}")
                    return True
                except Exception as interaction_error:
                    logger.warning(f" 🔄 Método de interação falhou: {str(interaction_error)}")
                    time.sleep(random.randint(2, 5))
            
            # Se todos os métodos falharem
            raise Exception("Nenhum método de interação funcionou")
        
        except Exception as e:
            logger.warning(f" 🚫 Erro na tentativa {tentativa + 1}: {str(e)}")
            time.sleep(random.randint(3, 7))
    
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
