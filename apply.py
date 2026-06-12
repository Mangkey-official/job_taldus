import os
import time
import ssl
import asyncio
import urllib3
import httpx
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from telegram import Bot

# --- 설정 구간 ---
TOKEN = '8837154747:AAGml9Wh7NC1GNiCPZMt1IDd1rpG-G-df0k'
CHAT_ID = '2035161254'
HISTORY_FILE = 'history.txt'
URL = "https://www.jobkorea.co.kr/Search/?stext=정보보안 취약점진단 모의해킹 침해대응"
# ----------------

# 1. SSL 인증 검증을 아예 끕니다. (보안이 엄격한 환경에서의 필수 조치)
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

# 이제 기존에 사용하던 send_message 함수를 그대로 사용해도 됩니다.
from telegram import Bot
import asyncio

async def send_message(text):
    bot = Bot(token=TOKEN) # request 옵션 없이 기본 설정
    await bot.send_message(chat_id=CHAT_ID, text=text)

def get_job_data():
    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(URL)
    time.sleep(7) 

    jobs = []
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        href = link.get_attribute("href")
        text = link.text.strip()
        # Recruit가 포함된 링크가 곧 채용 공고 상세페이지입니다.
        if href and "Recruit" in href and len(text) > 5:
            jobs.append({"title": text, "link": href})
    driver.quit()
    return jobs

def main():
    if not os.path.exists(HISTORY_FILE): open(HISTORY_FILE, 'w').close()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    jobs = get_job_data()
    
    for job in jobs:
        if job['link'] not in history:
            msg = f"🔔 [새로운 보안 공고]\n{job['title']}\n\n👉 바로가기: {job['link']}"
            asyncio.run(send_message(msg))
            
            with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
                f.write(job['link'] + '\n')
            print(f"알림 발송 완료: {job['title']}")

if __name__ == "__main__":
    main()