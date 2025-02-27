from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import asyncio
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import auth

app = FastAPI()



@app.get('/')
async def root():
    return {"message": "Hello World"}


