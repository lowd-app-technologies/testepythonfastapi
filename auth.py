from fastapi import APIRouter
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time
import requests
from pathlib import Path

router = APIRouter()

def save_image(image_url: str, image_name: str):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            Path("static/images").mkdir(parents=True, exist_ok=True)
            image_path = Path("static/images") / image_name
            with open(image_path, 'wb') as file:
                file.write(response.content)
            return f"/static/images/{image_name}"
        else:
            return None
    except Exception as e:
        return None

class Credentials(BaseModel):
    username: str
    password: str

@router.post("/get_user_info/")  
async def get_user_info(credentials: Credentials):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Novo modo headless mais estável
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")  
    chrome_options.add_argument("--disable-plugins")  
    chrome_options.add_argument("--disable-translate")  
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get("https://www.instagram.com/")
        time.sleep(3)

        username_input = driver.find_element(By.NAME, "username")
        password_input = driver.find_element(By.NAME, "password")

        username_input.send_keys(credentials.username)
        password_input.send_keys(credentials.password)
        password_input.send_keys(Keys.RETURN)

        time.sleep(10)
        
        driver.get("https://www.instagram.com/accounts/edit/")

        time.sleep(15)

        profile_picture = driver.find_element(By.XPATH, "//img[@alt='Alterar foto do perfil']")
        user_name = driver.find_element(By.XPATH, "//span[contains(@class, 'x1lliihq')]")

        profile_picture_src = profile_picture.get_attribute("src")
        
        image_name = f"{credentials.username}_profile.jpg"
        profile_picture_url = save_image(profile_picture_src, image_name)

        if profile_picture_url:
            return {
                "message": "Usuário autenticado com sucesso!",
                "user_name": user_name.text,
                "profile_picture": profile_picture_url 
            }
        else:
            return {"error": "Falha ao salvar a imagem do perfil."}
    
    except Exception as e:
        return {"error": str(e)}
    
    finally:
        driver.quit()
