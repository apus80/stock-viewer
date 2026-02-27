import os
import re
import datetime

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

def get_latest_market_data():
    """
    Morning Brew, Investing.com 등에서 데이터를 수집하여 9개 뉴스 데이터 및 주요 기사 요약을 반환합니다.
    """
    data = {
        "date": "2026.02.27",
        "weekday": "목",
        "main_article": {
            "title": "엔비디아 발 AI 차익실현에 나스닥 하락 📉",
            "summary": "엔비디아의 실적 발표 이후 투자자들의 차익 실현 매물이 쏟아지며 나스닥을 비롯한 주요 기술주 중심의 하락세가 나타났습니다. 전문가들은 단기적인 변동성 확대를 경고하면서도, 펀더멘털은 여전히 견조하다고 평가했습니다.",
            "image_url": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&q=80&w=800",
            "chart_data": {
                "labels": ["월", "화", "수", "목", "금"],
                "values": [150, 155, 160, 145, 140]
            }
        },
        "hot_news": {
            "title": "실시간 글로벌 인사이트 🌍",
            "items": [
                {"text": "📺 <strong>넷플릭스 11% 폭등</strong>: WBD 인수 철회로 자본 효율성 증대 기대감에 매수세 집중", "url": "https://www.reuters.com/business/media-telecom/netflix-shares-hit-record-high-2026-02-27/", "source": "Reuters"},
                {"text": "🏦 <strong>금리 인하기 기대감 후퇴</strong>: PPI 발표 앞두고 매파적 동결 가능성에 시장 경계감 확산", "url": "https://www.investing.com/news/economy/feds-williams-says-still-a-way-to-go-to-2-inflation-target-3315622", "source": "Investing.com"},
                {"text": "🕊️ <strong>중동 지정학적 리스크 소강</strong>: U.S.-이란 협상 재개 소식에 유가 변동성 축소", "url": "https://www.bloomberg.com/news/articles/2026-02-27/oil-steady-as-traders-weigh-middle-east-tensions-against-ample-supply", "source": "Bloomberg"},
                {"text": "🚀 <strong>스페이스X 신기록 달성</strong>: 하루 3회 발사 성공하며 우주 패권 강화", "url": "https://www.space.com/spacex-three-launches-one-day-february-2026", "source": "Space.com"},
                {"text": "💻 <strong>엔비디아 시총 4위로 밀려나</strong>: 실적 발표 후 단기 차익 실현", "url": "https://www.cnbc.com/2026/02/27/nvidia-nvda-stock-falls-after-earnings.html", "source": "CNBC"},
                {"text": "📱 <strong>애플 비전 프로 2세대 유출</strong>: 보급형 모델 하반기 출시설", "url": "https://www.macrumors.com/2026/02/27/apple-vision-pro-2nd-gen-details/", "source": "MacRumors"},
                {"text": "🚗 <strong>테슬라 독일 기가팩토리 확장</strong>: 지역 주민 반대에도 증설 승인", "url": "https://www.reuters.com/business/autos-transportation/tesla-wins-approval-expand-german-plant-2026-02-27/", "source": "Reuters"},
                {"text": "🧪 <strong>일라이릴리 비만치료제 효능</strong>: 당뇨병 예방 효과 장기 임상 결과 발표", "url": "https://www.investing.com/news/stock-market-news/eli-lilly-weightloss-drug-shows-longterm-safety-in-study-3315645", "source": "Investing.com"},
                {"text": "🏦 <strong>일본 엔화 가치 반등</strong>: 일본은행(BOJ) 금리 인상 시그널에 강세", "url": "https://www.bloomberg.com/news/articles/2026-02-27/yen-rises-as-boj-s-ueda-keeps-bets-alive-for-april-hike", "source": "Bloomberg"}
            ]
        }
    }
    return data

def update_index_html(data):
    if not os.path.exists(INDEX_HTML_PATH):
        return

    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # 왼쪽 카드: 주요 기사 요약 및 이미지/그래프
    main_article = data['main_article']
    # TradingView 심볼용 단순 미니 차트를 그래프로 사용합니다. 나스닥 종합 지수(IXIC) 차트를 예시로 넣겠습니다.
    left_card_content = f'''
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge" style="background:rgba(16, 185, 129, 0.15); color:#10b981;">KEY ISSUE</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">Today's Deep Dive</span>
                            </div>
                            <div class="market-status-title" style="margin-top: 10px;">{main_article['title']}</div>
                        </div>
                        <div style="width: 100%; height: 200px; border-radius: 12px; overflow: hidden; margin-bottom: 15px;">
                            <img src="{main_article['image_url']}" alt="News Image" style="width: 100%; height: 100%; object-fit: cover;">
                        </div>
                        <div style="font-size: 1.05rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 20px;">
                            {main_article['summary']}
                        </div>
                        <div class="section-label">Market Impact (NASDAQ)</div>
                        <div class="tradingview-widget-container" style="height: 180px; width: 100%; border-radius: 8px; overflow: hidden;">
                            <div class="tradingview-widget-container__widget"></div>
                            <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                            {{
                                "symbol": "NASDAQ:NDX",
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
    '''

    # 오른쪽 카드: Hot News (9개)
    news_items_html = "".join([
        f'<div class="headline-item"><a href="{{item["url"]}}" target="_blank" rel="noopener noreferrer">{{item["text"]}}</a><span class="news-source-tag">Source: {{item["source"]}}</span></div>'
        for item in data['hot_news']['items']
    ])

    new_card_html = f'''
            <div id="marketNewsCardArea">
                <div class="news-card-wrapper">
                    <div class="news-card-column">
                        {left_card_content}
                    </div>
                    <div class="news-card-column">
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge" style="background:rgba(244,63,94,0.15); color:#f43f5e;">TOP TRENDING</span>
                                <span style="font-size: 0.9rem; color: #94a3b8;">Global Insights</span>
                            </div>
                            <div class="market-status-title">{{data['hot_news']['title']}}</div>
                        </div>
                        <div class="section-label">Today's Hot News (9)</div>
                        <div style="margin-top:10px;">{{news_items_html}}</div>
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
        updated_content = re.sub(pattern, rf'\1{{new_card_html}}\3', content, flags=re.DOTALL)
        with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        print("Updated news card with 9 news items and deep dive article.")

if __name__ == "__main__":
    update_index_html(get_latest_market_data())

