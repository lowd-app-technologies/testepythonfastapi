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
    """
    Adiciona usuários ao Close Friends com estratégias avançadas
    """
    try:
        # Log de início do processo
        logger.info(" 🚀 Iniciando processo de adicionar usuários ao Close Friends")
        
        # Navegar diretamente para a página de Close Friends
        try:
            driver.get("https://www.instagram.com/accounts/close_friends/")
            logger.info(" 🌐 Navegou diretamente para URL de Close Friends")
            
            # Espera para carregar a página
            time.sleep(random.randint(5, 10))
            
            # Verificar se está na página correta
            current_url = driver.current_url
            logger.info(f" 🔍 URL atual: {current_url}")
            
            if 'close_friends' not in current_url:
                logger.warning(" ⚠️ Não está na página de Close Friends")
                
                # Tentar navegar via menu
                try:
                    menu_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/close_friends')]"))
                    )
                    menu_button.click()
                    logger.info(" 🔘 Navegou via botão de menu")
                    time.sleep(random.randint(3, 7))
                except Exception as menu_error:
                    logger.error(f" ❌ Erro ao navegar via menu: {str(menu_error)}")
                    raise
        
        except Exception as nav_error:
            logger.error(f" 💥 Erro crítico de navegação: {str(nav_error)}")
            
            # Capturar screenshot de diagnóstico
            screenshot_path = os.path.join(os.getcwd(), 'diagnostico_screenshots', f'close_friends_nav_error_{int(time.time())}.png')
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)
            logger.info(f" 📸 Screenshot de diagnóstico salva em: {screenshot_path}")
            
            raise
        
        # Localizar lista de seguidores para adicionar
        try:
            followers_list = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Adicionar ao Close Friends"]')
            logger.info(f" 📊 Total de seguidores encontrados: {len(followers_list)}")
            
            if not followers_list:
                logger.warning(" ⚠️ Nenhum seguidor encontrado para adicionar")
                return 0
        
        except Exception as list_error:
            logger.error(f" ❌ Erro ao localizar lista de seguidores: {str(list_error)}")
            raise
        
        # Processar seguidores em lotes
        total_adicionados = processar_seguidores_otimizado(driver, followers_list, modo='rapido')
        
        logger.info(f" 🏁 Processo concluído. Total de seguidores adicionados: {total_adicionados}")
        return total_adicionados
    
    except Exception as e:
        logger.critical(f" 💥 Erro crítico no processo: {str(e)}")
        
        # Capturar screenshot do estado final
        try:
            screenshot_path = os.path.join(os.getcwd(), 'diagnostico_screenshots', f'close_friends_process_error_{int(time.time())}.png')
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)
            logger.info(f" 📸 Screenshot de erro salva em: {screenshot_path}")
        except Exception as screenshot_error:
            logger.error(f" ❌ Erro ao capturar screenshot: {str(screenshot_error)}")
        
        raise

def adicionar_seguidor_close_friends(driver, follower, max_tentativas=5):
    """
    Tenta adicionar seguidor específico ao Close Friends
    """
    for tentativa in range(max_tentativas):
        try:
            logger.info(f" 🔄 Tentativa {tentativa + 1} de adicionar seguidor")
            
            # Estratégias de localização do botão de adicionar
            try:
                # Localizar botão de adicionar Close Friends
                add_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Adicionar ao Close Friends"]'))
                )
                
                # Rolar até o elemento se necessário
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_button)
                time.sleep(1)
                
                # Tentar métodos de clique
                interaction_methods = [
                    lambda: add_button.click(),  # Método padrão
                    lambda: driver.execute_script("arguments[0].click();", add_button),  # JavaScript
                    lambda: ActionChains(driver).move_to_element(add_button).click().perform(),  # Action Chains
                ]
                
                # Tentar cada método de interação
                for method in interaction_methods:
                    try:
                        method()
                        logger.info(f" ✅ Seguidor adicionado com sucesso na tentativa {tentativa + 1}")
                        return True
                    except Exception as interaction_error:
                        logger.warning(f" 🔄 Método de interação falhou: {str(interaction_error)}")
                        time.sleep(random.randint(2, 5))
                
                raise Exception("Nenhum método de clique funcionou")
            
            except Exception as locator_error:
                logger.warning(f" 🚫 Erro ao localizar botão: {str(locator_error)}")
                time.sleep(random.randint(3, 7))
        
        except Exception as e:
            logger.warning(f" 🚫 Erro na tentativa {tentativa + 1}: {str(e)}")
            time.sleep(random.randint(3, 7))
    
    logger.error(f" 💥 Falha ao adicionar seguidor após {max_tentativas} tentativas")
    return False

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
