import os
import sqlite3
from dotenv import load_dotenv
import re
from flask import Flask, jsonify,request
import yfinance as yf
import pandas as pd
from openai import OpenAI
from bs4 import BeautifulSoup
import time
import requests
#from pyppeteer import launch  # 비동기 웹 페이지 캡처용
import threading
from playwright.async_api import async_playwright
from PIL import Image
import datetime
import schedule
import asyncio
from threading import Thread
import pandas_ta as ta
import sqlite3
import base64
import json


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

# Flask 애플리케이션이 시작될 때 지침 파일을 한 번만 읽어 저장
instructions_path = "instructions.md"
instructions = None

# 종목 코드와 키워드 매핑
keyword_to_code = {
    '두산': '000150',
    '삼성전자': '005930',
    '하이브': '352820',
    '카카오': '035720',
    '한일시멘트': '300720'
}

# 지침 파일 읽기
def load_instructions(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        print(f"Instruction file '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the instruction file: {e}")
        return None

# 지침 파일 읽어오기
def initialize_instructions():
    global instructions
    instructions = load_instructions(instructions_path)
    if not instructions:
        print("Failed to load instructions. The application might not work as expected.")
        
        
def news_crawling(keyword):
    response = requests.get(f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={keyword}")
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("div.info_group")
    articles_data = []

    for article in articles:
        links = article.select("a.info")
        if len(links) >= 2:
            url = links[1].attrs["href"]
            response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            title = soup.select_one(".media_end_head_headline")
            content = soup.select_one("#dic_area")

            if title and content:
                articles_data.append({
                    "title": title.text.strip(),
                    "body": content.text.strip()
                })

            time.sleep(0.3)

    return articles_data

def summarize_article(article_body):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "다음 뉴스 기사를 요약해줘. 요약할 때 주식 향후 흐름을 예측하는 데 도움이 될 수 있도록 중요한 경제 지표, 기업 실적, 업계 동향, 주요 인물의 발언, 정책 변화 등을 중점적으로 요약해줘. 각 요약은 3~5문장 이내로 간결하게 작성해줘.단, 한국어로 작성해줘야해!"},
                {"role": "user", "content": article_body}
            ]
        )
        summary = response.choices[0].message.content
        #print("요약성공")
        return summary
    except Exception as e:
        print(f"Error in summarizing article with GPT-4: {e}")
        return None

def analyze_news_with_gpt4(news_data):
    try:
        summaries = []
        for article in news_data:
            if 'body' in article:
                summary = summarize_article(article['body'])
                summaries.append({
                    "title": article['title'],
                    "summary": summary
                })

        final_summary = "\n\n".join([summary['summary'] for summary in summaries])
        return final_summary
    except Exception as e:
        print(f"Error in analyzing data with GPT-4: {e}")
        return None
    
def summarize_final_summary(final_summary):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "다음 10개의 뉴스 요약본을 바탕으로 종합적인 최종 요약본을 작성해줘. 최종 요약본은 주식 시장의 향후 흐름을 예측하는 데 도움이 되도록 경제 지표, 기업 실적, 업계 동향, 주요 인물의 발언, 정책 변화 등을 중점적으로 요약해줘. 최종 요약본은 한국어로 3-5 문장으로 작성해줘."},
                {"role": "user", "content": final_summary}
            ]
        )
        final_summary_result = response.choices[0].message.content
        return final_summary_result
    except Exception as e:
        print(f"Error in summarizing final summary with GPT-4: {e}")
        return None

def get_news_data_for_keywords(keyword_to_code):
    results = []
    for keyword, code in keyword_to_code.items():
        news_data = news_crawling(keyword)
        if news_data:
            final_summary = analyze_news_with_gpt4(news_data)
            if final_summary:
                final_summary_result = summarize_final_summary(final_summary)
                if final_summary_result:
                    results.append({
                        "code": code,
                        "summary": final_summary_result
                    })
                else:
                    results.append({
                        "code": code,
                        "summary": "Failed to get the final summary."
                    })
            else:
                results.append({
                    "code": code,
                    "summary": "Failed to summarize articles."
                })
        else:
            results.append({
                "code": code,
                "summary": "Failed to retrieve news data."
            })
    return results

@app.route('/api/news-summary', methods=['GET'])
def news_summary():
    try:
        summaries = get_news_data_for_keywords(keyword_to_code)
        response = {
            "data": summaries
        }
        #print("반환")
        #json 응답
        return jsonify(response)

    except Exception as e:
        #오류 발생시
        return jsonify({"error": "에러발생"}), 500
    

@app.route('/api/finance', methods=['GET'])
def get_finance_data():
    ticker_symbol = request.args.get('ticker', type=str)
    period = request.args.get('period', type=str)
    interval = request.args.get('interval', type=str)
    
    try:
        data = fetch_finance_data(ticker_symbol, period, interval)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_finance_data(ticker_symbol, period, interval):
    ticker = yf.Ticker(ticker_symbol)
    data = ticker.history(period=period, interval=interval)
    data['timestamp'] = data.index.astype('int64')//10**6
    # Print data structure for debugging
    #print(data.head())
    
    # Select necessary columns
    data = data[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # Convert DataFrame to list of dictionaries
    return data.to_dict(orient='records')

# 분석에 사용하는 시세 데이터

def initialize_database():
    """
    데이터베이스 파일과 테이블을 생성하는 함수입니다.
    """
    db_path = os.getenv('DATABASE_URL', 'finance_database.db')
    
    conn = sqlite3.connect(db_path)  # SQLite 데이터베이스에 연결 (파일이 없으면 자동으로 생성됨)
    cursor = conn.cursor()

    # 테이블 생성 쿼리
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_data (
        Date TIMESTAMP,
        Open REAL,
        High REAL,
        Low REAL,
        Close REAL,
        Volume INTEGER,
        Stock_Code TEXT,
        SMA_10 REAL,
        EMA_10 REAL,
        RSI_15 REAL,
        STOCH_K REAL,
        STOCH_D REAL,
        MACD REAL,
        Signal_Line REAL,
        MACD_Histogram REAL,
        Middle_Band REAL,
        Upper_Band REAL,
        Lower_Band REAL,
        PRIMARY KEY (Date, Stock_Code)
    )
    ''')

    conn.commit()
    conn.close()

db_path = os.getenv('DATABASE_URL', 'finance_database.db')
def load_finance_data(code):
    """
    주어진 주식 코드에 대해 주식 시세 데이터를 가져오고, 기술적 지표를 추가한 후
    SQLite 데이터베이스에 저장하는 함수입니다.
    """
    ticker_symbol = code + '.ks'  # 주식 코드에 '.ks' 접미사를 붙여서 KRX 상장 주식 심볼을 만듭니다.
    
    try:
        # 주식 데이터 가져오기
        ticker = yf.Ticker(ticker_symbol)  # yfinance를 이용해 주식 데이터 가져오기
        data = ticker.history(period="3mo", interval="1h")  # 최근 3개월 동안의 1시간 간격 데이터를 가져옵니다.
        data.index = data.index.tz_localize(None)  # 타임존 정보를 제거하여 데이터의 인덱스를 로컬 시간으로 변환합니다.
        
        df_hourly = data[['Open', 'High', 'Low', 'Close', 'Volume']]  # 필요한 열만 선택합니다.

        
        # 기술적 지표를 추가하는 함수 정의
        def add_indicators(df):
            """
            주어진 데이터프레임에 기술적 지표를 추가하는 함수입니다.
            """
            df = df.copy()  # 원본 데이터프레임을 복사하여 변경을 방지합니다.

            # 이동 평균 (Simple Moving Average)
            df['Stock_Code'] = code
            df['SMA_10'] = ta.sma(df['Close'], length=10)  # 10기간 단순 이동 평균 추가
            df['EMA_10'] = ta.ema(df['Close'], length=10)  # 10기간 지수 이동 평균 추가

            # RSI (Relative Strength Index)
            df['RSI_15'] = ta.rsi(df['Close'], length=15)  # 15기간 RSI 추가

            # Stochastic Oscillator
            stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=5, smooth_k=5)  # Stochastic Oscillator 지표 추가
            df = df.join(stoch)  # 원본 데이터프레임에 Stochastic Oscillator 지표를 추가합니다.

            # MACD (Moving Average Convergence Divergence)
            ema_fast = df['Close'].ewm(span=12, adjust=False).mean()  # 12기간 빠른 지수 이동 평균
            ema_sLow = df['Close'].ewm(span=26, adjust=False).mean()  # 26기간 느린 지수 이동 평균
            df['MACD'] = ema_fast - ema_sLow  # MACD 값 계산
            df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()  # Signal Line 계산
            df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']  # MACD Histogram 계산

            # Bollinger Bands (볼린저 밴드)
            df['Middle_Band'] = df['Close'].rolling(window=15).mean()  # 15기간 중간 밴드
            std_dev = df['Close'].rolling(window=15).std()  # 15기간 표준 편차
            df['Upper_Band'] = df['Middle_Band'] + (std_dev * 2)  # 상단 밴드
            df['Lower_Band'] = df['Middle_Band'] - (std_dev * 2)  # 하단 밴드

            return df

        # 기술적 지표를 데이터프레임에 추가
        df_hourly = add_indicators(df_hourly)
        
        # SQLite 데이터베이스에 저장
        conn = sqlite3.connect(db_path)  # SQLite 데이터베이스에 연결 (파일이 없으면 자동으로 생성됨)
        # 기존 데이터 삭제
        conn.execute("DELETE FROM stock_data WHERE Stock_Code = ?", (code,))
        
        df_hourly.to_sql('stock_data', conn, if_exists='append', index=True)  # 데이터프레임을 'stock_data' 테이블에 저장
        conn.close()  # 데이터베이스 연결 종료

        return "Data saved to database successfully."

    except Exception as e:
        return f"An error occurred: {e}"
    
def get_stock_data(code):
    """
    주어진 주식 코드에 대한 데이터프레임을 반환하는 함수입니다.
    주식 코드에 대한 데이터를 SQLite 데이터베이스에서 조회합니다.

    :param code: 주식 코드
    :return: 데이터프레임 (pandas DataFrame)
    """
    try:
        # SQLite 데이터베이스에 연결
        conn = sqlite3.connect(db_path)
        
        # 데이터프레임 조회
        query = "SELECT * FROM stock_data WHERE Stock_Code = ?"
        df = pd.read_sql_query(query, conn, params=(code,))
        # 데이터의 샘플만 선택 (예: 최근 30일)
        df = df.tail(20) 
        conn.close()

        # 데이터프레임이 비어 있는 경우 처리
        if df.empty:
            print(f"No data found for the provided stock code: {code}")
            return None
        
        
        
        return df

    except Exception as e:
        print(f"An error occurred while fetching stock data: {e}")
        return None    
    
# 개형 캡처
async def capture_screenshot(code, file_path):
    url = f"https://finance.naver.com/item/fchart.naver?code={code}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)

        # 페이지 로드가 완료될 때까지 기다리기
        await page.wait_for_selector('//*[@id="content"]')

        # 보조지표 클릭
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[1]/div/div[2]/cq-menu/span')

        # 볼린저 밴드 클릭
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[1]/div/div[2]/cq-menu/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[2]/cq-label')

        # MACD 클릭
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[1]/div/div[2]/cq-menu/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[9]/cq-label')

        # RSI 클릭
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[1]/div/div[2]/cq-menu/cq-menu-dropdown/cq-scroll/cq-studies/cq-studies-content/cq-item[12]/cq-label')

        # 날짜 범위 선택
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[2]/cq-show-range/div[1]')

        # 분 단위 범위 선택
        await page.click('//div[@stxtap="rangeSetMin()"]')

        # 10분 범위 선택
        await page.click('//*[@id="content"]/div[2]/cq-context/div[1]/div[2]/cq-menu/cq-menu-dropdown/cq-item[4]')

        # 스크롤 내려서 완전히 로드되도록 하기
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.252);')

        # 스크린샷을 찍기 전에 페이지가 완전히 로드될 때까지 기다리기
        await page.wait_for_selector('//*[@id="content"]')

        # 스크린샷 저장
        await page.screenshot(path=file_path, full_page=True)

        # 브라우저 종료
        await browser.close()

        # 이미지 자르기
        image = Image.open(file_path)
        img_width, img_height = image.size

        # 자를 영역 설정 (여기서는 예시로 설정합니다)
        left = 150
        top = 450
        right = 750# 이미지가 지정된 너비보다 작을 수 있으므로 min 사용
        bottom =  min(img_height, 1000)  # 높이도 적절히 조정

        # 자르기
        cropped_image = image.crop((left, top, right, bottom))

        # 자른 이미지 저장
        cropped_image.save(file_path)
        
#주기적 캡쳐 저장
async def schedule_screenshots():
    while True:
        now = datetime.datetime.now()
        print("시작")
        # 특정 시간에만 캡처 (테스트용)
        if now.hour == 15 and now.minute == 16:
            
            for keyword, code in keyword_to_code.items():
                # 캡처 파일을 저장할 폴더 경로
                save_folder = 'screenshots'
                # 폴더가 존재하지 않으면 생성
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder)
                # 파일 경로 설정
                file_path = os.path.join(save_folder, f'screenshot_{code}.png')
                #file_path = f'screenshot_{code}.png'
                await capture_screenshot(code, file_path)
                print("캡처완료!")
                load_finance_data(code)
                print("저장완료")
                
        # 특정 시간에만 캡처 (테스트용)
        if now.hour == 14 and now.minute == 00:
            for keyword, code in keyword_to_code.items():
                save_folder = 'screenshots'
                # 폴더가 존재하지 않으면 생성
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder)
                # 파일 경로 설정
                file_path = os.path.join(save_folder, f'screenshot_{code}.png')
                await capture_screenshot(code, file_path)
                print("캡처완료2")
                load_finance_data(code)
                
        #진짜
        if now.weekday() < 5:  # 월~금
            if now.hour in [9, 12, 15]:
                for keyword, code in keyword_to_code.items():
                    save_folder = 'screenshots'
                    # 폴더가 존재하지 않으면 생성
                    if not os.path.exists(save_folder):
                        os.makedirs(save_folder)
                    # 파일 경로 설정
                    file_path = os.path.join(save_folder, f'screenshot_{code}.png')
                    await capture_screenshot(code, file_path)
                    load_finance_data(code)
        await asyncio.sleep(60)  # 1분마다 현재 시간 확인

def run_scheduled_tasks():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(schedule_screenshots())
    except KeyboardInterrupt:  # KeyboardInterrupt 예외 처리 추가
        print("스케줄된 작업이 중단되었습니다.")
    finally:
        loop.close()  # 이벤트 루프 종료

def extract_json_from_advice(advice):
    """
    주어진 응답 문자열에서 JSON 형식의 부분만 추출합니다.
    
    :param advice: GPT 응답 문자열
    :return: 추출된 JSON 객체 또는 None
    """
    # JSON 객체를 추출하기 위한 정규 표현식
    json_pattern = re.compile(r'\{.*?\}', re.DOTALL)
    
    # 정규 표현식으로 JSON 객체 추출
    match = json_pattern.search(advice)
    
    if match:
        json_str = match.group(0)
        try:
            # JSON 문자열을 Python 객체로 변환
            parsed_json = json.loads(json_str)
            return parsed_json
        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {e}")
            return None
    else:
        print("No JSON object found in the response.")
        return None
    
# gpt의 결정! 
def analyze_data_with_gpt4(news_data, data_json, last_decisions, current_status, personal_data, code):
    try:
        # 스크린샷 파일 경로 설정
        screenshot_folder = 'screenshots'
        screenshot_path = os.path.join(screenshot_folder, f'screenshot_{code}.png')
        
        # 스크린샷 파일을 Base64로 인코딩
        if os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            
            # 이미지 페이로드 생성
            image_payload = {
                "role": "user",
                "content": "",
                "attachments": [
                    {
                        "type": "image/png",
                        "data": image_base64
                    }
                ]
            }
        else:
            print(f"Screenshot not found: {screenshot_path}")
            image_payload = None

        data_json = data_json.to_json(orient='records')
        # 메시지 목록 생성
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": news_data},
            {"role": "user", "content": data_json},  # 데이터가 구조적일 경우 JSON으로 변환
            {"role": "user", "content": json.dumps(last_decisions)},  # 마찬가지로 JSON으로 변환
            {"role": "user", "content": json.dumps(current_status)},
            {"role": "user", "content": json.dumps(personal_data)}
        ]
        
        # 이미지가 있으면 메시지에 추가
        if image_payload:
            messages.append(image_payload)
        print("지피티 호출")
        # GPT-4 API 호출
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages
        )
        #print(response)
        #print("요기다!") 
        advice = response.choices[0].message.content
        #print("여긴가?!")
        #print(advice)
        # JSON 객체만 추출
        parsed_json = extract_json_from_advice(advice)
        
        if not parsed_json:
            raise ValueError("Extracted JSON is invalid or not found.")

        
        # reason 부분 번역
        if 'reason' in parsed_json:
            reason = parsed_json['reason']
            translated_reason = translate(reason)
            parsed_json['reason'] = translated_reason
        
        return parsed_json

    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    
def translateToEng(tendency):
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Translate the input sentence into English. Don't forget to print in English!"},
            {"role": "user", "content": tendency}
        ]
    )
    translation = response.choices[0].message.content
    return translation    
    
def translate(tendency):
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Translate the input sentence into Korean. Don't forget to print in Korean!"},
            {"role": "user", "content": tendency}
        ]
    )
    translation = response.choices[0].message.content
    return translation  
    
@app.route('/api/gpt-decision', methods=['POST'])
def handle_decision_request():
    try:
        #print("마사까")
        data = request.json
        #print("설마")
        # 요청 데이터에서 필요한 정보 추출
        stock_code = data.get('stockCode')
        start_day = data.get('startDay')  # 자동매매 시작일
        now = data.get('now')  # 현재 날짜 및 시간
        end_day = data.get('endDay')  # 자동매매 종료일
        investment_propensity = data.get('investmentPropensity')  # 투자 성향
        investment_insight = data.get('investmentInsight')  # 주관적 예측
        news_data = data.get('companyNews')
        stock_data = get_stock_data(stock_code)
        last_decisions = data.get('decisions', [])  # 최대 3개로 제한
        # 정렬: decisiontime이 최신인 것부터 정렬 (가정: decisiontime은 ISO 형식의 문자열)
        last_decisions_sorted = sorted(last_decisions, key=lambda x: x.get('decisionTime', ''), reverse=True)
        # 최근 3개만 가져오기
        last_decisions_recent = last_decisions_sorted[:3]
        #print("결정 받아오는 건 된다.")
        available_buy_amount = data.get('availableBuyAmount')  # From request
        current_price = data.get('currentPrice')  # From request
        
        if not stock_code:
            return jsonify({"error": "Stock code is required"}), 400


        # 가장 최근의 stockBalance 가져오기
        stock_balance = data.get('lastStockBalance')
            
        for decision in last_decisions:
            if 'reason' in decision:
                # 원래 reason
                original_reason = decision['reason']
                
                # reason 번역
                translated_reason = translateToEng(original_reason)
                
                # reason 업데이트
                decision['reason'] = translated_reason
                #print("이유번역")
                #print(translated_reason)
            
        # 현재 상태를 current_status에 묶어서 전달
        current_status = {
            'start_day': start_day,
            'now': now,
            'end_day': end_day,
            'available_buy_amount': available_buy_amount,
            'current_price': current_price,
            'stock_balance': stock_balance
        }
        tendency = translateToEng(investment_propensity)
        insight = translateToEng(investment_insight)
        # 개인 주관 데이터를 personal_data에 묶어서 전달
        personal_data = {
            'investment_propensity': tendency,
            'investment_insight': insight
        }
        #print("뭐지")
    except Exception as e:
        return jsonify({"error!!": str(e)}), 500
    
    # 예외가 발생하지 않은 경우 실행되는 부분
    max_retries = 5
    retry_delay_seconds = 5
    decision = None
    
    for attempt in range(max_retries):
        try:
            #print("일단여기까지")
            # GPT-4와의 상호작용을 통해 결정을 얻으려고 시도
            #print(last_decisions)
            advice = analyze_data_with_gpt4(
                news_data=news_data,
                data_json=stock_data,
                last_decisions=last_decisions_recent,
                current_status=current_status,
                personal_data=personal_data,
                code=stock_code
            )
            if advice is None:
                raise ValueError("Received advice is None.")
            print(advice)
            decision = advice
            return decision
        except (ValueError, json.JSONDecodeError) as e:
            print(f"JSON parsing failed: {e}. Retrying in {retry_delay_seconds} seconds...")
            time.sleep(retry_delay_seconds)
            print(f"Attempt {attempt + 2} of {max_retries}")
    
    if not decision:
        print("Failed to make a decision after maximum retries.")
        return jsonify({"error": "Failed to make a decision after maximum retries."}), 500
    
if __name__ == '__main__':
    # 스케줄러를 별도의 스레드에서 실행
    try:
        initialize_database()
        # 스케줄러를 별도의 스레드에서 실행
        
        # 지침 파일을 읽어오는 초기화 함수 호출
        initialize_instructions()
    
        scheduler_thread = Thread(target=run_scheduled_tasks)
        scheduler_thread.daemon = True  # 스레드를 데몬으로 설정하여 메인 프로그램 종료 시 스레드도 종료
        scheduler_thread.start()

        # Flask 앱 실행
        
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:  # Flask 서버의 KeyboardInterrupt 예외 처리
        print("Flask 서버가 중단되었습니다.")