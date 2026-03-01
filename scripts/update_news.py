import os
import re
import sys
import html as html_lib
import datetime
import urllib.request
import xml.etree.ElementTree as ET
try:
    import yfinance as yf
except ImportError:
    yf = None

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

MONTH_MAP = {
    'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
    'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'
}

def esc(text):
    return html_lib.escape(str(text))

def parse_rfc2822_date(pub):
    """'Sun, 01 Mar 2026 10:41:50 +0900' → '2026-03-01'"""
    try:
        parts = pub.strip().split()
        if len(parts) >= 4:
            d, m, y = parts[1], parts[2], parts[3]
            return f"{y}-{MONTH_MAP.get(m, m)}-{d.zfill(2)}"
    except:
        pass
    return ''

def truncate(text, n=90):
    text = re.sub(r'\s+', ' ', text).strip()
    return (text[:n] + '...') if len(text) > n else text

# ─── freezine.co.kr 뉴스 수집 ────────────────────────────────────────────────

def get_freezine_news(count=5):
    """
    전체 기사: RSS(gn_rss_allArticle.xml) — title, link, desc, date
    주식/증권: HTML 스크래핑(sc_section_code=S1N1) — title, link, desc, date
    """
    BASE = "https://www.freezine.co.kr"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    all_arts, stock_arts = [], []

    # 1) 전체 기사 — RSS
    try:
        req = urllib.request.Request(
            "https://cdn.freezine.co.kr/rss/gn_rss_allArticle.xml", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            root = ET.fromstring(r.read())
        for item in root.findall('.//item')[:count]:
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            desc  = truncate((item.findtext('description') or '').strip())
            date  = parse_rfc2822_date(item.findtext('pubDate') or '')
            if title and link:
                all_arts.append({'title': title, 'link': link, 'desc': desc, 'date': date})
        print(f"[freezine 전체기사] {len(all_arts)}건 로드")
    except Exception as e:
        print(f"[freezine RSS] 실패: {e}")

    # 2) 주식/증권 — HTML 스크래핑
    try:
        req = urllib.request.Request(
            f"{BASE}/news/articleList.html?sc_section_code=S1N1&view_type=sm",
            headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='replace')

        # view-cont 블록 추출
        blocks = re.findall(
            r'<div class="view-cont">(.*?)(?=<div class="view-cont"|<div[^>]*class="paging"|</ul>)',
            html, re.DOTALL)
        for blk in blocks[:count]:
            tm = re.search(r'class="titles".*?href="([^"]+)"[^>]*>\s*([^<]+)', blk, re.DOTALL)
            dm = re.search(r'<em>(\d{4}-\d{2}-\d{2})', blk)
            lm = re.search(r'<p class="lead">.*?<a[^>]*>(.*?)</a>', blk, re.DOTALL)
            if tm:
                href  = tm.group(1).strip()
                if href.startswith('/'): href = BASE + href
                title = tm.group(2).strip()
                date  = dm.group(1) if dm else ''
                lead  = truncate(re.sub(r'\s+', ' ', lm.group(1)).strip()) if lm else ''
                if title:
                    stock_arts.append({'title': title, 'link': href, 'desc': lead, 'date': date})
        print(f"[freezine 주식/증권] {len(stock_arts)}건 로드")
    except Exception as e:
        print(f"[freezine 주식] 실패: {e}")

    return all_arts, stock_arts

def build_news_items_html(arts, border='rgba(250,204,21,0.5)'):
    if not arts:
        return "<p style='color:#f87171;font-size:0.85em;margin:0;'>기사를 불러올 수 없습니다.</p>"
    out = ''
    for a in arts:
        desc_html = (
            f"<p style='color:#94a3b8;font-size:0.78em;margin:3px 0 0;"
            f"line-height:1.5;'>{esc(a['desc'])}</p>"
        ) if a.get('desc') else ''
        date_html = (
            f"<span style='color:#64748b;font-size:0.73em;display:block;margin-top:2px;'>"
            f"{esc(a['date'])}</span>"
        ) if a.get('date') else ''
        out += (
            f"<div style='margin-bottom:9px;padding:9px 10px;"
            f"background:rgba(0,0,0,0.2);border-left:3px solid {border};"
            f"border-radius:0 6px 6px 0;'>"
            f"<a href='{esc(a['link'])}' target='_blank' rel='noopener'"
            f" style='color:#f8fafc;text-decoration:none;font-size:0.87em;"
            f"font-weight:600;line-height:1.4;display:block;'>{esc(a['title'])}</a>"
            f"{date_html}{desc_html}</div>"
        )
    return out

# ─── 시장 데이터 수집 ─────────────────────────────────────────────────────────

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
            except:
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

    # freezine 뉴스 수집
    all_arts, stock_arts = get_freezine_news(5)

    data = {
        "is_morning_update": now_kst.hour in [7, 22],  # 오전 7시 + 오후 10시 KST
        "date": date_str,
        "weekday": weekday_str,
        "market": {
            "title": "실시간 시장 지표 & 섹터 현황 📊",
            "indices": indices_data,
            "sectors": sectors_data,
            "bigtech": bigtech_data,
            "korea": "실시간 글로벌 시장 변동에 따른 투자 심리 변화가 감지되고 있습니다. 주도 섹터 및 기관 수급 유입 상황을 주의 깊게 살펴보세요."
        },
        "freezine": {
            "all_arts":   all_arts,
            "stock_arts": stock_arts,
            "updated_time": now_kst.strftime("%H:%M")
        }
    }
    return data

# ─── HTML 업데이트 ────────────────────────────────────────────────────────────

def update_index_html(data):
    if not os.path.exists(INDEX_HTML_PATH):
        return

    with open(INDEX_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- 왼쪽 카드 HTML ---
    indices_html = "".join([
        f'<div class="mini-box"><span class="mini-name">{idx["name"]}</span>'
        f'<span class="mini-val">{idx["val"]}</span>'
        f'<span class="mini-pct {"change-up" if idx["up"] else "change-down"}">'
        f'{"▲" if idx["up"] else "▼"} {idx["pct"]}</span></div>'
        for idx in data['market']['indices']
    ])
    sectors_html = "".join([
        f'<div class="data-bar-row"><div class="data-bar-label"><span>{s["name"]}</span>'
        f'<div class="data-bar-visual"><div class="data-bar-fill" style="width:{s["val"]}; background:{s["color"]};"></div></div></div>'
        f'<span class="{"change-up" if "+" in s["pct"] else "change-down"}">{s["pct"]}</span></div>'
        for s in data['market']['sectors']
    ])
    bigtech_html = "".join([
        f'<div class="mini-box" style="padding:8px 4px;"><span class="mini-name" style="font-size:0.8rem;">{b["name"]}</span>'
        f'<span class="{"change-up" if b["up"] else "change-down"}" style="font-size:0.95rem; font-weight:700;">{b["pct"]}</span></div>'
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

    # --- 오른쪽 카드 HTML (freezine 뉴스 2섹션) ---
    fn = data['freezine']
    all_news_html   = build_news_items_html(fn['all_arts'],   border='rgba(250,204,21,0.5)')
    stock_news_html = build_news_items_html(fn['stock_arts'], border='rgba(56,189,248,0.5)')

    right_card_content = f'''
                        <div class="news-card-header">
                            <div class="header-top">
                                <span class="date-badge" style="background:rgba(245,158,11,0.15);color:#f59e0b;">프리진경제</span>
                                <span style="font-size:0.9rem;color:#94a3b8;">Updated: {fn['updated_time']} KST</span>
                            </div>
                            <div class="market-status-title" style="margin-top:10px;">📰 프리진경제 뉴스 브리핑</div>
                        </div>
                        <div style="margin-bottom:14px;">
                            <strong style="color:#facc15;font-size:0.82em;display:block;margin-bottom:8px;letter-spacing:0.03em;border-bottom:1px solid rgba(250,204,21,0.2);padding-bottom:4px;">📌 전체 기사</strong>
                            {all_news_html}
                        </div>
                        <div>
                            <strong style="color:#38bdf8;font-size:0.82em;display:block;margin-bottom:8px;letter-spacing:0.03em;border-bottom:1px solid rgba(56,189,248,0.2);padding-bottom:4px;">📈 주식·증권</strong>
                            {stock_news_html}
                        </div>
    '''

    # 업데이트 로직
    pattern = r'(<!-- MARKET_NEWS_CARD_START -->)(.*?)(<!-- MARKET_NEWS_CARD_END -->)'
    if not re.search(pattern, content, re.DOTALL):
        print("마커를 찾을 수 없습니다.")
        return

    left_html_to_use = left_card_content
    left_pattern = r'<!-- LEFT_CARD_START -->(.*?)<!-- LEFT_CARD_END -->'
    left_match = re.search(left_pattern, content, re.DOTALL)
    if left_match and not data['is_morning_update'] and '--force' not in sys.argv:
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
                        {right_card_content}
                        <!-- RIGHT_CARD_END -->
                    </div>
                </div>
            </div>
'''

    updated = re.sub(pattern, rf'\1{new_card_html}\3', content, flags=re.DOTALL)
    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(updated)
    print("index.html 업데이트 완료.")


if __name__ == "__main__":
    update_index_html(get_latest_market_data())
