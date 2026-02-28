import os
import re
import datetime
import urllib.request
import xml.etree.ElementTree as ET
try:
    import yfinance as yf
except ImportError:
    yf = None

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

def get_latest_market_data():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_kst = now_utc + datetime.timedelta(hours=9)
    date_str = now_kst.strftime("%Y.%m.%d")
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_str = weekdays[now_kst.weekday()]
    
    indices_map = {
        "DOW": "^DJI",
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "Russell 2K": "^RUT",
        "Phil. Semi": "^SOX",
        "VIX Index": "^VIX"
    }
    sectors_map = {
        "Financials (XLF)": "XLF",
        "Industrials (XLI)": "XLI",
        "Technology (XLK)": "XLK",
        "Health Care (XLV)": "XLV"
    }
    bigtech_map = ["MSFT", "AAPL", "NVDA", "GOOGL", "AMZN", "TSLA", "META"]
    
    indices_data, sectors_data, bigtech_data = [], [], []
    
    if yf:
        for name, tk in indices_map.items():
            try:
                hist = yf.Ticker(tk).history(period="5d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
                indices_data.append({"name": name, "val": f"{curr:,.1f}", "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%", "up": pct>=0})
            except Exception as e:
                indices_data.append({"name": name, "val": "N/A", "pct": "0.00%", "up": True})
                
        for name, tk in sectors_map.items():
            try:
                hist = yf.Ticker(tk).history(period="5d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
                col = "#10b981" if pct>=0 else "#f43f5e"
                val_w = min(max(50 + pct*10, 10), 90)
                sectors_data.append({"name": name, "val": f"{val_w:.0f}%", "color": col, "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%"})
            except:
                sectors_data.append({"name": name, "val": "50%", "color": "#10b981", "pct": "0.00%"})
                
        for tk in bigtech_map:
            try:
                hist = yf.Ticker(tk).history(period="5d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
                bigtech_data.append({"name": tk, "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%", "up": pct>=0})
            except:
                bigtech_data.append({"name": tk, "pct": "0.00%", "up": True})
    else:
        indices_data = [{"name": n, "val": "로드실패", "pct": "0.00%", "up": True} for n in indices_map]
        sectors_data = [{"name": n, "val": "50%", "color": "#10b981", "pct": "0.00%"} for n in sectors_map]
        bigtech_data = [{"name": n, "pct": "0.00%", "up": True} for n in bigtech_map]

    rss_url = "https://news.google.com/rss/search?q=%EA%B8%80%EB%A1%9C%EB%B2%8C+%EC%A6%9D%EC%8B%9C+%EA%B2%BD%EC%A0%9C&hl=ko&gl=KR&ceid=KR:ko"
    news_html = ""
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            colors = ["#facc15", "#38bdf8", "#10b981"]
            for i, item in enumerate(root.findall('.//item')[:3]):
                title = item.find('title').text.rsplit(" - ", 1)[0]
                link = item.find('link').text
                c = colors[i % len(colors)]
                news_html += f"<div style='margin-bottom: 12px; padding: 12px; background: rgba(0,0,0,0.25); border-left: 4px solid {c}; border-radius: 6px;'><strong style='color:{c}; font-size: 0.9em;'>⚡ HOT TOPIC {i+1}</strong><br><a href='{link}' target='_blank' style='color: #fff; text-decoration: none; font-weight: bold; line-height: 1.4; display: block; margin-top: 6px;'>{title}</a></div>"
    except Exception as e:
        news_html = "<div style='color:#f87171;'>뉴스 데이터를 불러오는데 실패했습니다.</div>"

    data = {
        "is_morning_update": now_kst.hour == 7,
        "date": date_str,
        "weekday": weekday_str,
        "market": {
            "title": "실시간 시장 지표 & 섹터 현황 📊",
            "indices": indices_data,
            "sectors": sectors_data,
            "bigtech": bigtech_data,
            "korea": "실시간 글로벌 시장 변동에 따른 투자 심리 변화가 감지되고 있습니다. 주도 섹터 및 기관 수급 유입 상황을 주의 깊게 살펴보세요."
        },
        "morning_brew_summary": {
            "title": "📰 실시간 글로벌 헤드라인 브리핑",
            "summary": f"<div style='margin-bottom:10px; font-size:0.95em; color:#cbd5e1;'>웹에서 수집된 최신 글로벌 경제 뉴스입니다. 클릭하여 원문을 확인하세요.</div>{news_html}",
            "image_url": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&q=80&w=800",
            "link": "https://news.google.com/search?q=%EA%B8%80%EB%A1%9C%EB%B2%8C+%EC%A6%9D%EC%8B%9C+%EA%B2%BD%EC%A0%9C",
            "updated_time": now_kst.strftime("%p %I:%M")
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
                        <div style="font-size: 1.05rem; line-height: 1.7; color: #cbd5e1; margin-bottom: 20px; padding: 15px; border-left: 4px solid #f59e0b; background: rgba(255,255,255,0.03); border-radius: 0 8px 8px 0;">
                            {mb['summary']}
                        </div>
                        <div style="text-align: center; margin-top: 20px;">
                            <a href="{mb['link']}" target="_blank" rel="noopener noreferrer" style="display:inline-block; width:100%; padding:15px; background:linear-gradient(135deg, #f59e0b, #d97706); color:#fff; text-decoration:none; border-radius:12px; font-weight:800; font-size:1.1rem; box-shadow:0 10px 15px -3px rgba(0,0,0,0.3); transition:transform 0.2s; box-sizing:border-box;">
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

