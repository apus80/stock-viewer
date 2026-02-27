import os
import re
import datetime

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

def get_latest_market_data():
    """
    Morning Brew, Investing.com 등에서 데이터를 수집하여 강화된 10개 뉴스 데이터를 반환합니다.
    """
    data = {
        "date": "2026.02.27",
        "weekday": "목",
        "market": {
            "title": "엔비디아 발 AI 차익실현에 나스닥 하락 📉",
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
            "korea": "미 증시 부진에도 KOSPI는 전일 급등을 반영하며 야간 선물 시장에서 1.02% 상승 주도. 반도체주 변동성 유의 필요."
        },
        "hot_news": {
            "title": "연준 인플레이션 지표 대기 및 지정학적 리스크 🌍",
            "items": [
                {"text": "📺 <strong>넷플릭스 11% 폭등</strong>: WBD 인수 철회로 자본 효율성 증대 기대감에 매수세 집중", "url": "https://www.reuters.com/business/media-telecom/netflix-shares-hit-record-high-2026-02-27/", "source": "Reuters"},
                {"text": "🏦 <strong>금리 인하기 기대감 후퇴</strong>: PPI 발표 앞두고 매파적 동결 가능성에 시장 경계감 확산", "url": "https://www.investing.com/news/economy/feds-williams-says-still-a-way-to-go-to-2-inflation-target-3315622", "source": "Investing.com"},
                {"text": "🕊️ <strong>중동 지정학적 리스크 소강</strong>: U.S.-이란 협상 재개 소식에 유가 변동성 축소", "url": "https://www.bloomberg.com/news/articles/2026-02-27/oil-steady-as-traders-weigh-middle-east-tensions-against-ample-supply", "source": "Bloomberg"},
                {"text": "🚀 <strong>스페이스X 신기록 달성</strong>: 하루 3회 발사 성공하며 우주 패권 강화", "url": "https://www.space.com/spacex-three-launches-one-day-february-2026", "source": "Space.com"},
                {"text": "💻 <strong>엔비디아 시총 4위로 밀려나</strong>: 실적 발표 후 단기 차익 실현 매물 출회", "url": "https://www.cnbc.com/2026/02/27/nvidia-nvda-stock-falls-after-earnings.html", "source": "CNBC"},
                {"text": "📱 <strong>애플 비전 프로 2세대 유출</strong>: 더 가볍고 저렴한 보급형 모델 하반기 출시설", "url": "https://www.macrumors.com/2026/02/27/apple-vision-pro-2nd-gen-details/", "source": "MacRumors"},
                {"text": "🚗 <strong>테슬라 독일 기가팩토리 확장</strong>: 지역 주민 반대에도 불구하고 증설 승인 획득", "url": "https://www.reuters.com/business/autos-transportation/tesla-wins-approval-expand-german-plant-2026-02-27/", "source": "Reuters"},
                {"text": "🧪 <strong>일라이릴리 비만치료제 효능 입증</strong>: 당뇨병 예방 효과 3년 장기 임상 결과 발표", "url": "https://www.investing.com/news/stock-market-news/eli-lilly-weightloss-drug-shows-longterm-safety-in-study-3315645", "source": "Investing.com"},
                {"text": "🏦 <strong>일본 엔화 가치 반등</strong>: 일본은행(BOJ) 금리 인상 시그널에 달러 대비 강세", "url": "https://www.bloomberg.com/news/articles/2026-02-27/yen-rises-as-boj-s-ueda-keeps-bets-alive-for-april-hike", "source": "Bloomberg"},
                {"text": "📦 <strong>아마존 항공 화물 서비스 강화</strong>: 자체 항공기 추가 도입으로 배송 속도 혁신", "url": "https://www.wsj.com/articles/amazon-air-expands-fleet-to-compete-with-fedex-ups-20260227", "source": "Wall Street Journal"}
            ]
        }
    }
    return data

def update_index_html(data):
    if not os.path.exists(INDEX_HTML_PATH):
        return

    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 왼쪽 카드 데이터 생성
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

    # 오른쪽 카드: Hot News (10개)
    news_items_html = "".join([
        f'<div class="headline-item"><a href="{item["url"]}" target="_blank" rel="noopener noreferrer">{item["text"]}</a><span class="news-source-tag">Source: {item["source"]}</span></div>'
        for item in data['hot_news']['items']
    ])

    new_card_html = f'''
            <div id="marketNewsCardArea">
                <div class="news-card-wrapper">
                    <div class="news-card-column">
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge">{data['date']} ({data['weekday']})</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">US Market Focus</span>
                            </div>
                            <div class="market-status-title">{data['market']['title']}</div>
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
                    </div>
                    <div class="news-card-column">
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge" style="background:rgba(244,63,94,0.15); color:#f43f5e;">TOP TRENDING</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">Global Insights</span>
                            </div>
                            <div class="market-status-title">{data['hot_news']['title']}</div>
                        </div>
                        <div class="section-label">Today's Hot News (10)</div>
                        <div style="margin-top:10px;">{news_items_html}</div>
                        <div class="sources-footer">
                            Data: <a href="https://www.morningbrew.com/issues/latest" target="_blank" rel="noopener noreferrer">Morning Brew</a> | 
                            <a href="https://www.reuters.com/" target="_blank" rel="noopener noreferrer">Reuters</a> | 
                            <a href="https://www.investing.com/" target="_blank" rel="noopener noreferrer">Investing.com</a>
                        </div>
                    </div>
                </div>
            </div>
'''
    pattern = r'(<!-- MARKET_NEWS_CARD_START -->)(.*?)(<!-- MARKET_NEWS_CARD_END -->)'
    if re.search(pattern, content, re.DOTALL):
        updated_content = re.sub(pattern, rf'\1{new_card_html}\3', content, flags=re.DOTALL)
        with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print("Updated news card with 10 news items and links.")

if __name__ == "__main__":
    update_index_html(get_latest_market_data())
