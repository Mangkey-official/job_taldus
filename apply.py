import re
import os
import sys
import time
import ssl
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from telegram import Bot
from telegram.error import InvalidToken, TelegramError

# --- 설정 구간 ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
HISTORY_FILE = 'history.txt'

URL_BASE = "https://www.jobkorea.co.kr/Search/?stext=정보보안&careerType=2&cotype=1,4&Page_No="

KEYWORDS = ["정보보호", "정보보안", "취약점진단", "침해대응", "Red Team", "레드팀", "블루팀", "Security", "시큐리티", "보안", "보호", "클라우드", "정보", "화이트 해커"]

EXCLUDE_KEYWORDS = [
    "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원",
    "충북", "충남", "전북", "전남", "경북", "경남", "제주", "전체", "전국", "전지역",
    "대기업", "중견기업", "외국계", "공공기관", "공기업", "벤처기업", "스타트업",
    "연봉", "면접후", "협의", "이상", "이하", "만원", "시급", "월급", "기업 서비스", "성과급", "천재교과서",
    "정규직", "계약직", "인턴", "파견직", "신입", "경력", "무관", "학력", "고졸", "대졸", "초대졸",
    "상세지역", "근무지", "재택", "관심기업", "등록", "채용", "모집", "•",
    "복지", "복지포인트", "휴양시설", "광고", "경조사", "웰컴", "연차제도", "건강검진", "중국", "홍콩", "유류비지원",
    "유류비", "유연근무", "근무", "보험","휴가제도", "식사지원", "스크랩", "홈페이지 지원", "즉시 지원" "오늘 마감"
    "오늘 마감! 놓치지 마세요!"
]
# ----------------

os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context


async def send_message(bot: Bot, text: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, read_timeout=10, write_timeout=10)
        print("💡 [성공] 텔레그램 알림 발송 완료!")
    except InvalidToken:
        print("❌ [에러] 토큰이 올바르지 않습니다.")
    except TelegramError as e:
        print(f"❌ [텔레그램 에러] 발송 실패: {e}")

def check_keyword(title: str) -> bool:
    target_text = title.replace(" ", "")
    for keyword in KEYWORDS:
        if keyword.replace(" ", "") in target_text:
            return True
    return False

def clean_company_name(text: str) -> str:
    if not text:
        return "회사명 확인불가"
    cleaned = text.split('\n')[0]
    for word in ["관심기업", "등록", "별점", "확인"]:
        cleaned = cleaned.replace(word, "")
    return cleaned.strip()

def get_job_data():
    options = Options()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
   
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
   
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
   
    jobs = []
    page = 1
   
    while page <= 5:
        target_url = f"{URL_BASE}{page}"
        print(f"🔄 잡코리아 [{page} / 5 페이지] 수집 중...")
        driver.get(target_url)
       
        if page == 1:
            time.sleep(12)
        else:
            time.sleep(5)
           
        # 공고 링크(a 태그)를 기준으로 먼저 찾습니다.
        a_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'Recruit/GI_Read') or contains(@href, 'GI_No=')]")
       
        if not a_elements:
            print(f"🏁 더 이상 검색 결과 공고가 없습니다. [{page-1} 페이지]에서 탐색을 종료합니다.")
            break
           
        page_collected_count = 0
       
        for a_el in a_elements:
            try:
                title = a_el.text.strip()
                href = a_el.get_attribute("href")
                
                if not href or len(title) < 3:
                    continue
                
                # 중복 주소 제외
                if any(j['link'] == href for j in jobs):
                    continue
                
                current_company = "회사명 확인불가"
                
                # [핵심 로직] 디자인(클래스)을 무시하고, 링크 속성으로만 부모자식 관계를 추적합니다.
                try:
                    # 1. 공고 링크(a_el)에서 거슬러 올라가, '기업 정보 링크(Co_Read)'를 포함하고 있는 가장 가까운 부모 컨테이너(카드)를 찾습니다.
                    container = a_el.find_element(By.XPATH, "./ancestor::*[.//a[contains(@href, 'Co_Read') or contains(@href, 'Company')]][1]")
                    
                    # 2. 해당 컨테이너 내부에서 기업 정보 링크를 가져옵니다.
                    company_els = container.find_elements(By.XPATH, ".//a[contains(@href, 'Co_Read') or contains(@href, 'Company')]")
                    
                    for c_el in company_els:
                        txt = c_el.text.strip()
                        # 회사명이 비어있지 않고, 공고 제목과 다르며, 너무 길지 않은 경우 확정
                        if txt and txt != title and len(txt) <= 25:
                            current_company = clean_company_name(txt)
                            break
                except Exception:
                    pass
                
                # 만약 위 방법으로 실패했다면 (예: 링크가 없는 비공개 기업 등), 기존 텍스트 필터링 방식으로 안전하게 Fallback
                if current_company == "회사명 확인불가":
                    try:
                        fallback_container = a_el.find_element(By.XPATH, "../../../..")
                        spans = fallback_container.find_elements(By.XPATH, ".//span | .//div")
                        
                        for span in spans:
                            txt = span.text.strip()
                            if not txt or len(txt) > 25 or txt == title:
                                continue
                            is_garbage = False
                            for ex_key in EXCLUDE_KEYWORDS:
                            # 텍스트 내에 키워드가 조금이라도 포함되어 있으면 즉시 제외
                                if ex_key in txt:
                                    is_garbage = True
                                    break

                            # 추가로 특정 키워드가 포함되었을 때도 제외하고 싶다면 아래 조건 유지
                            if not is_garbage:
                                if any(k in txt for k in KEYWORDS): # 긍정 키워드가 포함된 경우
                                    pass 
    
                            # 숫자와 금액 단위가 섞인 광고성 텍스트 제거 로직
                            if any(char.isdigit() for char in txt) and any(w in txt for w in ["만", ",", "원"]):
                                is_garbage = True

                            if not is_garbage:
                                current_company = clean_company_name(txt)
                                break    
                            
                    except Exception:
                        pass
                
                jobs.append({
                    "company": current_company,
                    "title": title,
                    "link": href
                })
                page_collected_count += 1
                
            except Exception:
                continue
               
        print(f"📈 {page} 페이지에서 {page_collected_count}개의 공고를 확보했습니다.")
       
        if page_collected_count == 0 and page > 5:
            print(f"🏁 새로운 유효 공고 데이터가 없어 탐색을 조기 종료합니다.")
            break
           
        page += 1
        time.sleep(2)
       
    driver.quit()
    return jobs

async def main_async():
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, 'w', encoding='utf-8').close()
        
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    print("🔍 잡코리아 검색 페이지 크롤링을 시작합니다 (최대 5페이지)...")
    jobs = get_job_data()
    
    if not jobs:
        print("\n❌ 검색 결과 내에서 수집한 공고 데이터가 전혀 없습니다.")
        return

    print(f"\n📋 총 {len(jobs)}개의 공고 데이터를 확보했습니다. 알림 전송을 시작합니다.")
    print(f"🎯 타겟 키워드: {', '.join(KEYWORDS)}\n" + "="*40)

    found_new_jobs = False  # 새로운 공고가 있는지 확인하는 플래그

    try:
        async with Bot(token=TOKEN) as bot:
            for job in jobs:
                company = job['company']
                title = job['title']
                link = job['link']
                
                job_id = extract_job_id(link)
                
                # 이미 확인한 공고인지 체크
                if job_id in history:
                    continue
                    
                # 키워드 필터링 및 신입 제외 로직
                if check_keyword(title) or check_keyword(company):
                    if "신입" in title:
                        continue
                        
                    found_new_jobs = True # 새로운 공고가 있음을 표시
                    
                    msg = f"🔔 [새로운 맞춤 보안 공고]\n\n🏢 회사명: {company}\n📌 공고명: {title}\n\n👉 바로가기: {link}"
                    await send_message(bot, msg)
                    
                    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
                        f.write(job_id + '\n')
                    
                    await asyncio.sleep(1)
                else:
                    print(f"⏭️ [제외됨] {title} ({company})")

            # 루프가 끝난 후 새로운 공고가 하나도 없었을 때 처리
            if not found_new_jobs:
                print("\n✅ 새로운 공고가 없습니다.")
                await send_message(bot, "🔔 현재 확인된 새로운 맞춤 공고가 없습니다.")
                
    except InvalidToken:
        print("\n❌ [에러] 텔레그램 토큰을 다시 확인해주세요.")

    try:
        async with Bot(token=TOKEN) as bot:
            for job in jobs:
                company = job['company']
                title = job['title']
                link = job['link']
                
                # 💡 URL 전체가 아닌 고유 ID만 추출
                job_id = extract_job_id(link)
                
                # 💡 history.txt에는 고유 ID가 있는지 확인
                if job_id in history:
                    continue
                    
                if check_keyword(title) or check_keyword(company):
                    if "신입" in title:
                        continue
                        
                    msg = f"🔔 [새로운 맞춤 보안 공고]\n\n🏢 회사명: {company}\n📌 공고명: {title}\n\n👉 바로가기: {link}"
                    await send_message(bot, msg)
                    
                    # 💡 파일에 기록할 때도 긴 URL 대신 고유 ID만 기록
                    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
                        f.write(job_id + '\n')
                        
                    await asyncio.sleep(1)
                else:
                    print(f"⏭️ [제외됨] {title} ({company})")
    except InvalidToken:
        print("\n❌ [에러] 텔레그램 토큰을 다시 확인해주세요.")

def extract_job_id(url: str) -> str:
    """URL에서 잡코리아 고유 공고 번호만 추출합니다."""
    # GI_Read/ 뒤의 숫자 또는 GI_No= 뒤의 숫자를 찾습니다.
    match = re.search(r'(?:GI_Read/|GI_No=)(\d+)', url)
    if match:
        return match.group(1)
    
    # 만약 고유 번호를 찾지 못했다면 최후의 수단으로 URL 원본 반환
    return url

def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n👋 [안내] 사용자에 의해 프로그램이 강제 종료되었습니다.")

if __name__ == "__main__":
    main()
