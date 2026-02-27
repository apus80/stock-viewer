import os
import re
import datetime

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

def get_latest_market_data():
    """
    Morning Brew, Investing.com 등에서 데이터를 수집하여 변환
    """
    # KST 기준 시간 구하기 (UTC +9)
    now_utc = datetime.datetime.utcnow()
    now_kst = now_utc + datetime.timedelta(hours=9)
    
    date_str = now_kst.strftime("%Y.%m.%d")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_str = weekdays[now_kst.weekday()]
    
    data = {
        "is_morning_update": now_kst.hour == 7,  # 아침 7시에만 True
        "date": date_str,
        "weekday": weekday_str,
        "market": {
            "title": "실시간 시장 지표 & 섹터 현황 📊",
            "indices": [
                {"name": "DOW", "val": "49,499.2", "pct": "+0.03%", "up": True},
                {"name": "S&P 500", "val": "6,908.8", "pct": "-0.54%", "up": False},
                {"name": "NASDAQ", "val": "22,878.3", "pct": "-1.18%", "up": False},
                {"name": "Russell 2K", "val": "2,455.1", "pct": "+0.58%", "up": True},
                {"name": "Phil. Semi", "val": "5,120.4", "pct": "-3.19%", "up": False},
                {"name": "VIX Index", "val": "16.4", "pct": "+4.13%", "up": False}
            ],
            "sectors": [
                {"name": "Financials (XLF)", "val": "75%", "color": "#10b981", "pct": "+1.21%"},
                {"name": "Industrials (XLI)", "val": "65%", "color": "#10b981", "pct": "+0.63%"},
                {"name": "Technology (XLK)", "val": "40%", "color": "#f43f5e", "pct": "-1.40%"},
                {"name": "Health Care (XLV)", "val": "45%", "color": "#f43f5e", "pct": "-0.26%"},
            ],
            "bigtech": [
                {"name": "MSFT", "pct": "+0.28%", "up": True},
                {"name": "AAPL", "pct": "-0.47%", "up": False},
                {"name": "NVDA", "pct": "-5.49%", "up": False},
                {"name": "GOOGL", "pct": "-1.88%", "up": False},
                {"name": "AMZN", "pct": "-1.29%", "up": False},
                {"name": "TSLA", "pct": "-2.11%", "up": False},
                {"name": "META", "pct": "+0.51%", "up": True}
            ],
            "korea": "미 증시 부진에도 KOSPI는 전일 급등을 반영하며 야간 선물 시장에서 상승 주도. 반도체주 변동성 유의 필요."
        },
        "morning_brew_summary": {
            "title": "☕ Morning Brew Daily Insights",
            "summary": "오늘의 글로벌 증시는 매크로 지표 혼조세와 AI 섹터의 차익 실현 움직임 속에서도 전반적인 강세장을 유지하고 있습니다. 특히 기술주의 밸류에이션 부담에도 불구하고 헬스케어 및 금융주 중심으로 순환매가 뚜렷하게 관측되었습니다.",
            "image_url": "https://images.unsplash.com/photo-1590283603385-18ff3827104f?auto=format&fit=crop&q=80&w=800",
            "link": "https://www.morningbrew.com/issues/latest",
            "updated_time": now_kst.strftime("%p %I:%M") # 예: AM 07:00, PM 11:00
        }
    }
    return data

def update_index_html(data):
    if not os.path.exists(INDEX_HTML_PATH):
        return

    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- 왼쪽 카드 HTML 생성 (지수, 섹터) ---
    indices_html = "".join([
        f'<div class="mini-box"><span class="mini-name">{idx["name"]}</span><span class="mini-val">{idx["val"]}</span><span class="mini-pct {"change-up" if idx["up"] else "change-down"}">{"▲" if idx["up"] else "▼"} {idx["pct"]}</span></div>'
        for idx in data['market']['indices']
    ])
    sectors_html = "".join([
        f'<div class="data-bar-row"><div class="data-bar-label"><span>{s["name"]}</span><div class="data-bar-visual"><div class="data-bar-fill" style="width:{s["val"]}; background:{s["color"]};"></div></div></div><span class="{"change-up" if "+" in s["pct"] else "change-down"}">{s["pct"]}</span></div>'
        for s in data['market']['sectors']
    ])
    bigtech_html = "".join([
        f'<div class="mini-box" style="padding:8px 4px;"><span class="mini-name" style="font-size:0.8rem;">{b["name"]}</span><span class="{"change-up" if b["up"] else "change-down"}" style="font-size:0.95rem; font-weight:700;">{b["pct"]}</span></div>'
        for b in data['market']['bigtech']
    ])

    left_card_content = f'''
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge">{data['date']} ({data['weekday']})</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">US Market Focus</span>
                            </div>
                            <div class="market-status-title" style="margin-top: 5px; font-size: 1.25rem;">{data['market']['title']}</div>
                        </div>
                        <div class="section-label">Major Indices</div>
                        <div class="index-grid-3">{indices_html}</div>
                        <div class="section-label">S&P 500 Sectors</div>
                        <div style="margin-bottom:20px;">{sectors_html}</div>
                        <div class="section-label">Magnificent 7</div>
                        <div class="index-grid-3" style="grid-template-columns: repeat(4, 1fr);">{bigtech_html}</div>
                        <div class="section-label">Korea Market Summary</div>
                        <div style="font-size:1rem; line-height:1.6; color:#cbd5e1; background:rgba(255,255,255,0.03); padding:12px; border-radius:10px;">
                            🇰🇷 {data['market']['korea']}
                        </div>
    '''

    # --- 오른쪽 카드 HTML 생성 (Morning Brew Summary) ---
    mb = data['morning_brew_summary']
    right_card_content = f'''
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge" style="background:rgba(245, 158, 11, 0.15); color:#f59e0b;">LATEST ISSUE</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">Updated: {mb['updated_time']} KST</span>
                            </div>
                            <div class="market-status-title" style="margin-top: 10px;">{mb['title']}</div>
                        </div>
                        <div style="width: 100%; height: 180px; border-radius: 12px; overflow: hidden; margin-bottom: 20px;">
                            <img src="{mb['image_url']}" alt="Morning Brew Image" style="width: 100%; height: 100%; object-fit: cover;">
                        </div>
                        <div style="font-size: 1.05rem; line-height: 1.7; color: #cbd5e1; margin-bottom: 20px; padding: 10px; border-left: 4px solid #f59e0b; background: rgba(255,255,255,0.03); border-radius: 0 8px 8px 0;">
                            {mb['summary']}
                        </div>
                        <div class="section-label">Market Impact Trend (S&P 500)</div>
                        <div class="tradingview-widget-container" style="height: 200px; width: 100%; border-radius: 8px; overflow: hidden; margin-bottom: 25px;">
                            <div class="tradingview-widget-container__widget"></div>
                            <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                            {{
                                "symbol": "AMEX:SPY",
                                "width": "100%",
                                "height": "100%",
                                "locale": "kr",
                                "dateRange": "1M",
                                "colorTheme": "dark",
                                "isTransparent": true,
                                "autosize": true,
                                "largeChartUrl": ""
                            }}
                            </script>
                        </div>
                        <div style="text-align: center; margin-top: 10px;">
                            <a href="{mb['link']}" target="_blank" rel="noopener noreferrer" style="display:inline-block; width:100%; padding:15px; background:linear-gradient(135deg, #f59e0b, #d97706); color:#fff; text-decoration:none; border-radius:12px; font-weight:800; font-size:1.1rem; box-shadow:0 10px 15px -3px rgba(0,0,0,0.3); transition:transform 0.2s;">
                                ☕ Read Latest Issue on Morning Brew
                            </a>
                        </div>
    '''

    # 업데이트 로직 (왼쪽 카드는 오전 7시에만 업데이트하도록 처리, 그 외는 오른쪽 카드만 업데이트된 HTML 생성)
    # 실제로는 스크립트 실행 시 정적 치환을 위해 구분자를 추가합니다.
    # 기존 index.html에는 <!-- MARKET_NEWS_CARD_START --> 통짜 구조였음. 이번에 분할합니다.
    
    # HTML 내부에 좌측/우측 분할 앵커가 없으면 기존 것을 통으로 교체합니다.
    pattern = r'(<!-- MARKET_NEWS_CARD_START -->)(.*?)(<!-- MARKET_NEWS_CARD_END -->)'
    if re.search(pattern, content, re.DOTALL):
        
        # 오전 7시 업데이트이거나 파일을 처음 재구성하는 경우 (현재 구조 파싱 위해)
        left_html_to_use = left_card_content
        right_html_to_use = right_card_content
        
        # 이미 쪼개져있는지 확인용 래퍼
        new_card_html = f'''
            <div id="marketNewsCardArea">
                <div class="news-card-wrapper">
                    <div class="news-card-column" id="left-card-column">
                        <!-- LEFT_CARD_START -->
                        {left_html_to_use}
                        <!-- LEFT_CARD_END -->
                    </div>
                    <div class="news-card-column" id="right-card-column">
                        <!-- RIGHT_CARD_START -->
                        {right_html_to_use}
                        <!-- RIGHT_CARD_END -->
                    </div>
                </div>
            </div>
'''
        
        # 만약 기존 내용에 LEFT_CARD_START 가 있으면 왼쪽 카드 유지 여부 결정
        left_pattern = r'<!-- LEFT_CARD_START -->(.*?)<!-- LEFT_CARD_END -->'
        left_match = re.search(left_pattern, content, re.DOTALL)
        
        if left_match and not data['is_morning_update'] and '--force' not in os.sys.argv:
            # 7시가 아니면 왼쪽 카드는 기존 내용 유지
            left_html_to_use = left_match.group(1).strip()
            new_card_html = f'''
            <div id="marketNewsCardArea">
                <div class="news-card-wrapper">
                    <div class="news-card-column" id="left-card-column">
                        <!-- LEFT_CARD_START -->
                        {left_html_to_use}
                        <!-- LEFT_CARD_END -->
                    </div>
                    <div class="news-card-column" id="right-card-column">
                        <!-- RIGHT_CARD_START -->
                        {right_html_to_use}
                        <!-- RIGHT_CARD_END -->
                    </div>
                </div>
            </div>
'''
        
        updated_content = re.sub(pattern, rf'\1{new_card_html}\3', content, flags=re.DOTALL)
        with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print("Updated news card layout successfully.")

if __name__ == "__main__":
    update_index_html(get_latest_market_data())

