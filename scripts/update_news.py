import os
import re
import sys
import html as html_lib
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from deep_translator import GoogleTranslator
    def translate_ko(text):
        if not text:
            return text
        try:
            return GoogleTranslator(source='auto', target='ko').translate(text[:500]) or text
        except Exception:
            return text
except ImportError:
    def translate_ko(text):
        return text

# --- 설정 ---
INDEX_HTML_PATH = 'index.html'

MONTH_MAP = {
    'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
    'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

MK_RSS_SECTIONS = {
    '증권':    'https://www.mk.co.kr/rss/40300001/',
    '경제':    'https://www.mk.co.kr/rss/30100041/',
    '부동산':  'https://www.mk.co.kr/rss/50300009/',
    '국제':    'https://www.mk.co.kr/rss/30200030/',
    '산업·IT': 'https://www.mk.co.kr/rss/50200011/',
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
    except Exception:
        pass
    return ''

def truncate(text, n=90):
    text = re.sub(r'\s+', ' ', text).strip()
    return (text[:n] + '...') if len(text) > n else text

# ─── 뉴스 수집 ────────────────────────────────────────────────────────────────

def fetch_rss_news(url, count, source_name, source_url, do_translate=False):
    """범용 RSS 뉴스 수집 함수"""
    arts = []
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            root = ET.fromstring(r.read())
        for item in root.findall('.//item')[:count]:
            title = (item.findtext('title') or '').strip()
            link  = (item.findtext('link')  or '').strip()
            desc  = truncate((item.findtext('description') or '').strip())
            date  = parse_rfc2822_date(item.findtext('pubDate') or '')
            if title and link:
                arts.append({
                    'title': translate_ko(title) if do_translate else title,
                    'link': link, 'desc': desc, 'date': date,
                    'source': source_name, 'source_url': source_url
                })
        print(f"[{source_name}] {len(arts)}건 로드")
    except Exception as e:
        print(f"[{source_name}] 실패: {e}")
    return arts


def get_yahoo_finance_news(count=3):
    """Yahoo Finance RSS — 영어 기사 (한국어 번역)"""
    return fetch_rss_news(
        "https://finance.yahoo.com/news/rssindex", count,
        "Yahoo Finance", "https://finance.yahoo.com", do_translate=True
    )


def get_freezine_section_news(section_code, count=3, source_name='프리진경제'):
    """프리진경제 섹션 HTML 스크래핑 (BeautifulSoup)
    URL: https://www.freezine.co.kr/news/articleList.html?sc_section_code=S1N1&view_type=sm
    섹션 전용 기사 목록만 추출 (상단 featured/인기 기사 제외)
    """
    url = (f"https://www.freezine.co.kr/news/articleList.html"
           f"?sc_section_code={section_code}&view_type=sm")
    source_url = "https://www.freezine.co.kr"
    arts = []
    seen_links = set()

    if not BS4_OK:
        print(f"[{source_name}] BeautifulSoup 없음, 건너뜀")
        return arts

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='replace')

        soup = BeautifulSoup(html, 'html.parser')

        # ── 섹션 전용 기사 목록 컨테이너 탐색 ──────────────────────────────
        # 한국 뉴스 CMS 공통 패턴: #section-list, .list-block, .article-list 등
        # featured/인기 기사는 보통 다른 div에 있고 <li> 목록이 섹션 기사
        container = (
            soup.find(id='section-list') or          # <section id="section-list"> 포함
            soup.find(id='article-list') or
            soup.find('div', class_=re.compile(r'(article|news)[_\-]?list|list[_\-]?body', re.I)) or
            soup.find('ul',  class_=re.compile(r'(article|news)[_\-]?list', re.I))
        )

        # 컨테이너 내 <li> 기사 링크 우선 (섹션 목록은 보통 <li> 구조)
        if container:
            a_tags = container.find_all('a', href=re.compile(r'articleView\.html\?idxno='))
        else:
            # 컨테이너를 못 찾으면 전체 <li> 안의 링크만 추출
            a_tags = []
            for li in soup.find_all('li'):
                for a in li.find_all('a', href=re.compile(r'articleView\.html\?idxno=')):
                    a_tags.append(a)
            # 그래도 없으면 전체 페이지 (마지막 fallback)
            if not a_tags:
                a_tags = soup.find_all('a', href=re.compile(r'articleView\.html\?idxno='))

        for a_tag in a_tags:
            title = a_tag.get_text(strip=True)
            href  = a_tag.get('href', '')

            # 너무 짧은 텍스트(네비·버튼 등) 제외
            if not title or len(title) < 8:
                continue

            # 절대 URL 변환
            if href.startswith('/'):
                href = 'https://www.freezine.co.kr' + href
            elif not href.startswith('http'):
                href = 'https://www.freezine.co.kr/' + href.lstrip('/')

            if href in seen_links:
                continue
            seen_links.add(href)

            # 날짜: 부모 <li> 또는 <div> 안에서 YYYY.MM.DD / YYYY-MM-DD 패턴
            date = ''
            parent = a_tag.find_parent('li') or a_tag.find_parent('div')
            if parent:
                m = re.search(r'(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})', parent.get_text(' '))
                if m:
                    date = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

            arts.append({
                'title': title,
                'link':  href,
                'desc':  '',
                'date':  date,
                'source': source_name,
                'source_url': source_url
            })
            if len(arts) >= count:
                break

        print(f"[{source_name}] {len(arts)}건 로드 (container={'found' if container else 'fallback'})")
    except Exception as e:
        print(f"[{source_name}] 실패: {e}")

    return arts


def get_freezine_stock_news(count=3):
    """프리진경제 주식/증권 (S1N1)"""
    return get_freezine_section_news('S1N1', count, '프리진경제 주식/증권')


def get_freezine_intl_news(count=3):
    """프리진경제 국제/IT (S1N6)"""
    return get_freezine_section_news('S1N6', count, '프리진경제 국제/IT')


# ─── CBOE / FRED 데이터 ───────────────────────────────────────────────────────

def get_cboe_pc_ratio(filename):
    """CBOE Put/Call 비율 CSV (공개 데이터, 무료)"""
    url = f"https://www.cboe.com/publishing/scheduledtask/mktdata/datahouse/{filename}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read().decode('utf-8', errors='replace')
        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        for line in reversed(lines):
            parts = line.split(',')
            if len(parts) >= 2:
                val_str = parts[1].strip().strip('"').strip()
                date_str = parts[0].strip().strip('"').strip()
                try:
                    ratio = float(val_str)
                    if 0.1 < ratio < 10.0:   # 유효 범위 체크
                        return ratio, date_str
                except ValueError:
                    continue
    except Exception as e:
        print(f"[CBOE {filename}] 실패: {e}")
    return None, None


def get_fred_latest(series_id, units=None):
    """FRED 공개 CSV에서 최신값 (API 키 불필요)
    예: DFF(Fed금리), CPIAUCSL(CPI), UNRATE(실업률)
    units='pc1' → YoY % 변화율
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    if units:
        url += f"&units={units}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            content = r.read().decode('utf-8', errors='replace')
        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        for line in reversed(lines[1:]):      # 헤더 스킵
            parts = line.split(',')
            if len(parts) >= 2 and parts[1].strip() not in ('', '.'):
                try:
                    return float(parts[1].strip()), parts[0].strip()
                except ValueError:
                    continue
    except Exception as e:
        print(f"[FRED {series_id}] 실패: {e}")
    return None, None




def get_cnn_fear_greed():
    """CNN Fear & Greed Index (무료 공개 API)
    score 0-24: Extreme Fear, 25-44: Fear, 45-55: Neutral, 56-75: Greed, 76-100: Extreme Greed
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        fg = data.get('fear_and_greed', {})
        score = fg.get('score')
        rating = fg.get('rating', '')
        prev   = fg.get('previous_close')
        if score is not None:
            return {
                'score':  round(float(score), 1),
                'rating': rating,
                'prev':   round(float(prev), 1) if prev is not None else None
            }
    except Exception as e:
        print(f"[CNN F&G] 실패: {e}")
    return {}


def get_spy_options_pcr():
    """SPY 옵션 데이터에서 실시간 Put/Call 비율 계산 (yfinance)"""
    if not yf:
        return None
    try:
        spy = yf.Ticker("SPY")
        exps = spy.options
        if not exps:
            return None
        chain = spy.option_chain(exps[0])
        call_vol = float(chain.calls['volume'].fillna(0).sum())
        put_vol  = float(chain.puts['volume'].fillna(0).sum())
        if call_vol > 0:
            return round(put_vol / call_vol, 2)
    except Exception as e:
        print(f"[SPY PCR] 실패: {e}")
    return None

def get_volatility_macro_data():
    """변동성(VIX), P/C 비율(CBOE), 매크로(FRED/yfinance) 통합 수집"""
    vm = {
        'vix': None, 'vix_prev': None, 'vix_52h': None, 'vix_52l': None,
        'total_pcr': None, 'equity_pcr': None, 'index_pcr': None, 'pcr_date': None,
        'spy_pcr': None,
        'tnx': None, 'irx': None, 'spread': None,
        'dff': None, 'cpi_yoy': None, 'unrate': None,
        'dxy': None, 'gold': None,
        'fg_score': None, 'fg_rating': '', 'fg_prev': None,
    }

    # VIX & 금리 / 자산가격 (yfinance)
    if yf:
        try:
            hist = yf.Ticker("^VIX").history(period="1y")
            if not hist.empty:
                vm['vix'] = round(float(hist['Close'].iloc[-1]), 2)
                if len(hist) >= 2:
                    vm['vix_prev'] = round(float(hist['Close'].iloc[-2]), 2)
                vm['vix_52h'] = round(float(hist['Close'].max()), 2)
                vm['vix_52l'] = round(float(hist['Close'].min()), 2)
        except Exception as e:
            print(f"[VIX] 실패: {e}")

        for ticker, key in [("^TNX", "tnx"), ("^IRX", "irx"),
                            ("DX-Y.NYB", "dxy"), ("GC=F", "gold")]:
            try:
                h = yf.Ticker(ticker).history(period="5d")
                if not h.empty:
                    vm[key] = round(float(h['Close'].iloc[-1]), 2)
            except Exception as e:
                print(f"[{ticker}] 실패: {e}")

        if vm['tnx'] is not None and vm['irx'] is not None:
            vm['spread'] = round(vm['tnx'] - vm['irx'], 2)

    # CBOE P/C 비율 (실패 시 SPY 옵션으로 대체)
    vm['total_pcr'],  vm['pcr_date'] = get_cboe_pc_ratio("totalpc.csv")
    vm['equity_pcr'], _              = get_cboe_pc_ratio("equitypc.csv")
    vm['index_pcr'],  _              = get_cboe_pc_ratio("indexpc.csv")

    # SPY 옵션 P/C (CBOE 실패 시 fallback)
    spy_pcr = get_spy_options_pcr()
    if vm['total_pcr'] is None:
        vm['total_pcr'] = spy_pcr
    vm['spy_pcr'] = spy_pcr

    # CNN Fear & Greed Index
    fg = get_cnn_fear_greed()
    vm['fg_score']  = fg.get('score')
    vm['fg_rating'] = fg.get('rating', '')
    vm['fg_prev']   = fg.get('prev')

    # FRED 매크로 (공개 CSV)
    vm['dff'],     _ = get_fred_latest("DFF")              # Fed 기준금리
    vm['cpi_yoy'], _ = get_fred_latest("CPIAUCSL", "pc1")  # CPI YoY %
    vm['unrate'],  _ = get_fred_latest("UNRATE")           # 실업률

    print(f"[변동성] VIX={vm['vix']} PCR-total={vm['total_pcr']} "
          f"DFF={vm['dff']} CPI={vm['cpi_yoy']} UR={vm['unrate']}")
    return vm


def _vbadge(label, cls):
    return f'<span class="vol-badge vol-badge-{cls}">{label}</span>'


def _vix_badge(v):
    if v is None: return ''
    if v < 15:  return _vbadge('낮음', 'green')
    if v < 20:  return _vbadge('보통', 'lgreen')
    if v < 25:  return _vbadge('⚠️중간', 'yellow')
    if v < 30:  return _vbadge('⚠️높음', 'orange')
    return _vbadge('🔴공포', 'red')


def _pcr_badge(v):
    if v is None: return ''
    if v < 0.7:  return _vbadge('과열', 'red')
    if v < 1.0:  return _vbadge('중립', 'yellow')
    return _vbadge('방어', 'green')


def _spread_badge(v):
    if v is None: return ''
    if v >= 0.5:  return _vbadge('정상', 'green')
    if v >= 0.0:  return _vbadge('평탄', 'yellow')
    return _vbadge('역전', 'red')


def _cpi_badge(v):
    if v is None: return ''
    if v < 2.5:  return _vbadge('안정', 'green')
    if v < 4.0:  return _vbadge('주의', 'yellow')
    return _vbadge('고물가', 'red')


def _dff_badge(v):
    if v is None: return ''
    if v < 2.0:  return _vbadge('완화', 'green')
    if v < 4.0:  return _vbadge('중립', 'yellow')
    return _vbadge('긴축', 'orange')


def _fmtv(v, suffix='', prefix='', dec=2):
    """None-safe 포맷"""
    if v is None: return 'N/A'
    return f"{prefix}{v:.{dec}f}{suffix}"


def build_volatility_card_html(vm, updated_time):
    """변동성 & 매크로 위젯 HTML 생성"""

    # ── CNN F&G ──
    fg_s   = vm.get('fg_score')
    fg_r   = vm.get('fg_rating', '')
    fg_p   = vm.get('fg_prev')
    if fg_s is None:
        fg_display = 'N/A'
        fg_badge   = ''
    else:
        fg_display = f'{fg_s:.0f}/100'
        if   fg_s <= 24: fg_badge = _vbadge('극도공포', 'red')
        elif fg_s <= 44: fg_badge = _vbadge('공포', 'orange')
        elif fg_s <= 55: fg_badge = _vbadge('중립', 'yellow')
        elif fg_s <= 75: fg_badge = _vbadge('탐욕', 'lgreen')
        else:            fg_badge = _vbadge('극도탐욕', 'green')

    fg_delta = ''
    if fg_s is not None and fg_p is not None:
        d = fg_s - fg_p
        col_fg = '#4ade80' if d >= 0 else '#f87171'
        fg_delta = f'<span style="color:{col_fg};font-size:0.68rem;margin-left:2px;">{"▲" if d>=0 else "▼"}{abs(d):.1f}</span>'

    fg_rating_ko = {'Extreme Fear':'극도공포', 'Fear':'공포', 'Neutral':'중립',
                    'Greed':'탐욕', 'Extreme Greed':'극도탐욕'}.get(fg_r, fg_r)

    # ── VIX 관련 사전 계산 ──
    vix_str   = _fmtv(vm['vix'])
    vix_badge = _vix_badge(vm['vix'])

    if vm['vix'] is not None and vm['vix_prev'] is not None:
        delta = vm['vix'] - vm['vix_prev']
        arrow = '▲' if delta > 0 else '▼'
        col   = '#f87171' if delta > 0 else '#4ade80'
        vix_delta = (f'<span style="color:{col};font-size:0.68rem;margin-left:2px;">'
                     f'{arrow}{abs(delta):.2f}</span>')
    else:
        vix_delta = ''

    if (vm['vix'] is not None and vm['vix_52h'] is not None
            and vm['vix_52l'] is not None):
        rng = vm['vix_52h'] - vm['vix_52l']
        pct_pos = ((vm['vix'] - vm['vix_52l']) / rng * 100) if rng > 0 else 50
        vix_rank = f'상위 {100 - pct_pos:.0f}%'
    else:
        vix_rank = 'N/A'

    vix_52_str  = f"{_fmtv(vm['vix_52l'])} ~ {_fmtv(vm['vix_52h'])}"

    # ── P/C 관련 ──
    spy_pcr_str = _fmtv(vm.get('spy_pcr'))
    spy_pcr_b   = _pcr_badge(vm.get('spy_pcr'))
    total_pcr_str  = _fmtv(vm['total_pcr'])
    total_pcr_b    = _pcr_badge(vm['total_pcr'])
    equity_pcr_str = _fmtv(vm['equity_pcr'])
    equity_pcr_b   = _pcr_badge(vm['equity_pcr'])
    index_pcr_str  = _fmtv(vm['index_pcr'])
    index_pcr_b    = _pcr_badge(vm['index_pcr'])

    tpcr = vm['total_pcr'] if vm['total_pcr'] is not None else 0.85
    pcr_signal = ('풋 우세 · 하락 헤지' if vm['index_pcr'] is not None
                  and vm['index_pcr'] > 1.0 else '콜 우세 · 낙관')

    # ── 금리 / 자산 ──
    tnx_str    = _fmtv(vm['tnx'], '%')
    irx_str    = _fmtv(vm['irx'], '%')
    spread_str = _fmtv(vm['spread'], '%')
    spread_b   = _spread_badge(vm['spread'])
    spread_col = '#4ade80' if (vm['spread'] or 0) >= 0 else '#f87171'
    dxy_str    = _fmtv(vm['dxy'], dec=1)
    gold_str   = _fmtv(vm['gold'], prefix='$', dec=0)

    # ── FRED 매크로 ──
    dff_str     = _fmtv(vm['dff'])
    dff_badge   = _dff_badge(vm['dff'])
    cpi_str     = _fmtv(vm['cpi_yoy'])
    cpi_badge   = _cpi_badge(vm['cpi_yoy'])
    unrate_str  = _fmtv(vm['unrate'])

    pcr_date_str = vm['pcr_date'] or ''

    return f"""            <div class="vol-macro-card">
                <div class="vol-macro-header">
                    <span class="vol-macro-title">📊 시장 심리 &amp; 매크로 현황</span>
                    <span style="font-size:0.7rem;color:#475569;">Updated: {updated_time} KST · 매시 자동갱신 · CBOE / FRED / yfinance</span>
                </div>
                <div class="vol-macro-grid">

                    <!-- ① 변동성 & 공포 지표 -->
                    <div>
                        <div class="vol-section-title">😱 변동성 &amp; 공포 지표</div>
                        <div class="vol-metric-row" style="margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.07);">
                            <span class="vol-metric-label">CNN 공포탐욕지수</span>
                            <span class="vol-metric-value" style="font-size:0.9rem;">{fg_display} {fg_delta} {fg_badge}</span>
                        </div>
                        <div class="vol-metric-row" style="margin-bottom:6px;">
                            <span class="vol-metric-label" style="color:#64748b;font-size:0.71rem;">분류</span>
                            <span class="vol-metric-value" style="color:#94a3b8;font-size:0.72rem;">{fg_rating_ko}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">VIX 공포지수</span>
                            <span class="vol-metric-value">{vix_str} {vix_delta} {vix_badge}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">52주 범위</span>
                            <span class="vol-metric-value" style="color:#64748b;font-size:0.71rem;">{vix_52_str}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">52주 위치</span>
                            <span class="vol-metric-value" style="color:#64748b;font-size:0.71rem;">{vix_rank}</span>
                        </div>
                        <div class="vol-metric-row" style="margin-top:7px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.05);">
                            <span class="vol-metric-label">Total P/C 비율</span>
                            <span class="vol-metric-value">{total_pcr_str} {total_pcr_b}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">Equity P/C</span>
                            <span class="vol-metric-value">{equity_pcr_str} {equity_pcr_b}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">Index P/C</span>
                            <span class="vol-metric-value">{index_pcr_str} {index_pcr_b}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">SPY P/C (실시간)</span>
                            <span class="vol-metric-value">{spy_pcr_str} {spy_pcr_b}</span>
                        </div>
                        <div style="margin-top:5px;font-size:0.64rem;color:#374151;">{pcr_date_str} CBOE / yfinance</div>
                    </div>

                    <!-- ② 옵션 신호 & 금리 -->
                    <div>
                        <div class="vol-section-title">📈 옵션 신호 &amp; 금리</div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">미국 10년물</span>
                            <span class="vol-metric-value">{tnx_str}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">미국 3개월물</span>
                            <span class="vol-metric-value">{irx_str}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">장단기 스프레드</span>
                            <span class="vol-metric-value" style="color:{spread_col};">{spread_str} {spread_b}</span>
                        </div>
                        <div class="vol-metric-row" style="margin-top:7px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.05);">
                            <span class="vol-metric-label">Index P/C 신호</span>
                            <span class="vol-metric-value" style="font-size:0.7rem;color:#94a3b8;">{pcr_signal}</span>
                        </div>
                        <div class="vol-metric-row" style="margin-top:4px;">
                            <span class="vol-metric-label">달러 DXY</span>
                            <span class="vol-metric-value">{dxy_str}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">금 ($/oz)</span>
                            <span class="vol-metric-value">{gold_str}</span>
                        </div>
                    </div>

                    <!-- ③ 월별 매크로 요약 -->
                    <div>
                        <div class="vol-section-title">🏦 월별 매크로 요약</div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">Fed 기준금리</span>
                            <span class="vol-metric-value">{dff_str}% {dff_badge}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">CPI 물가 YoY</span>
                            <span class="vol-metric-value">{cpi_str}% {cpi_badge}</span>
                        </div>
                        <div class="vol-metric-row">
                            <span class="vol-metric-label">실업률</span>
                            <span class="vol-metric-value">{unrate_str}%</span>
                        </div>
                        <div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);
                                    font-size:0.63rem;color:#374151;line-height:1.9;">
                            📌 P/C &lt;0.7 과열(빨강) · 0.7-1.0 중립(노랑) · &gt;1.0 방어(초록)<br>
                            📌 VIX &lt;15 안정 · 15-20 보통 · 20-25 주의 · &gt;25 공포<br>
                            📌 스프레드 양수=정상 · 음수=역전(침체신호)
                        </div>
                    </div>

                </div>
            </div>"""




def get_mk_rss_all_sections(count=3):
    """매일경제 RSS 섹션별 기사 수집 (드롭다운용)"""
    result = {}
    for section, url in MK_RSS_SECTIONS.items():
        arts = fetch_rss_news(url, count, f'매일경제({section})',
                              'https://www.mk.co.kr', do_translate=False)
        result[section] = arts
        print(f"[MK {section}] {len(arts)}건")
    return result


def build_mk_dropdown_html(mk_data):
    """MK RSS 드롭다운 HTML.
    mkShow() 함수는 index.html 정적 <script>에 정의됨.
    여기서는 데이터 JSON + 셀렉트 박스 + 결과 div만 생성.
    """
    sections_data = {}
    for sec, arts in mk_data.items():
        sections_data[sec] = [
            {'t': a['title'], 'l': a['link'], 'd': a.get('date', '')}
            for a in arts
        ]
    # </script> 가 JSON 안에 있으면 HTML 파싱 종료 → \u003C 로 치환
    data_json = json.dumps(sections_data, ensure_ascii=False).replace('</', r'\u003C/')

    options_html = ''.join(
        '<option value="{s}" {sel}>{s}</option>'.format(
            s=s, sel='selected' if s == '증권' else ''
        )
        for s in mk_data.keys()
    )

    parts = [
        '<script>var _MKD=' + data_json + ';</script>',
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">',
        '<strong style="color:#fbbf24;font-size:0.82em;letter-spacing:0.03em;">📰 매일경제</strong>',
        '<select id="mk-cat-sel" onchange="mkShow(this.value)"',
        ' style="background:#1e2535;color:#f8fafc;border:1px solid rgba(255,255,255,0.15);',
        'border-radius:6px;padding:2px 10px;font-size:0.75rem;cursor:pointer;">',
        options_html,
        '</select></div>',
        '<div id="mk-articles-box"></div>',
        '<script>if(typeof mkShow==="function"){mkShow("증권");}</script>',
    ]
    return ''.join(parts)


def build_news_items_html(arts, border='rgba(250,204,21,0.5)'):
    if not arts:
        return "<p style='color:#f87171;font-size:0.85em;margin:0;'>기사를 불러올 수 없습니다.</p>"
    out = ''
    for a in arts:
        desc_html = (
            f"<p style='color:#94a3b8;font-size:0.78em;margin:3px 0 0;line-height:1.5;'>{esc(a['desc'])}</p>"
        ) if a.get('desc') else ''
        meta_parts = []
        if a.get('date'):
            meta_parts.append(esc(a['date']))
        if a.get('source'):
            meta_parts.append(
                f"출처: <a href='{esc(a.get('source_url', '#'))}' target='_blank' rel='noopener'"
                f" style='color:#94a3b8;text-decoration:underline;'>{esc(a['source'])}</a>"
            )
        meta_html = (
            f"<span style='color:#64748b;font-size:0.72em;display:block;margin-top:3px;'>"
            f"{'  ·  '.join(meta_parts)}</span>"
        ) if meta_parts else ''
        out += (
            f"<div style='margin-bottom:9px;padding:9px 10px;"
            f"background:rgba(0,0,0,0.2);border-left:3px solid {border};"
            f"border-radius:0 6px 6px 0;'>"
            f"<a href='{esc(a['link'])}' target='_blank' rel='noopener'"
            f" style='color:#f8fafc;text-decoration:none;font-size:0.87em;"
            f"font-weight:600;line-height:1.4;display:block;'>{esc(a['title'])}</a>"
            f"{meta_html}{desc_html}</div>"
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
                indices_data.append({
                    "name": name, "val": f"{curr:,.1f}",
                    "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%", "up": pct >= 0
                })
            except Exception:
                indices_data.append({"name": name, "val": "N/A", "pct": "0.00%", "up": True})
        for name, tk in sectors_map.items():
            try:
                hist = yf.Ticker(tk).history(period="5d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
                col = "#10b981" if pct >= 0 else "#f43f5e"
                val_w = min(max(50 + pct * 10, 10), 90)
                sectors_data.append({
                    "name": name, "val": f"{val_w:.0f}%", "color": col,
                    "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%", "up": pct >= 0
                })
            except Exception:
                sectors_data.append({"name": name, "val": "50%", "color": "#10b981", "pct": "0.00%", "up": True})
        for tk in bigtech_map:
            try:
                hist = yf.Ticker(tk).history(period="5d")
                curr, prev = hist['Close'].iloc[-1], hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
                bigtech_data.append({"name": tk, "pct": f"{'+' if pct>=0 else ''}{pct:.2f}%", "up": pct >= 0})
            except Exception:
                bigtech_data.append({"name": tk, "pct": "0.00%", "up": True})
    else:
        indices_data = [{"name": n, "val": "로드실패", "pct": "0.00%", "up": True} for n in indices_map]
        sectors_data = [{"name": n, "val": "50%", "color": "#10b981", "pct": "0.00%", "up": True} for n in sectors_map]
        bigtech_data = [{"name": n, "pct": "0.00%", "up": True} for n in bigtech_map]

    # 변동성 & 매크로 수집
    vm_data = get_volatility_macro_data()

    # MK RSS 섹션별 기사 수집
    mk_data = get_mk_rss_all_sections(3)

    # 뉴스 수집 (3 소스 × 3 기사 = 9개)
    # Yahoo Finance 제거 (MK RSS 드롭다운으로 대체)
    stock_arts = get_freezine_stock_news(3)   # 프리진경제 주식/증권
    intl_arts  = get_freezine_intl_news(3)    # 프리진경제 국제/IT

    data = {
        "is_morning_update": now_kst.hour in [7, 22],
        "date": date_str,
        "weekday": weekday_str,
        "market": {
            "title": "실시간 시장 지표 & 섹터 현황 📊",
            "indices": indices_data,
            "sectors": sectors_data,
            "bigtech": bigtech_data,
            "korea": "실시간 글로벌 시장 변동에 따른 투자 심리 변화가 감지되고 있습니다. 주도 섹터 및 기관 수급 유입 상황을 주의 깊게 살펴보세요."
        },
        "volatility": vm_data,
        "mk_data": mk_data,
        "news": {
            "fz_stock":    stock_arts,
            "fz_intl":     intl_arts,
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
    indices_parts = []
    for idx in data['market']['indices']:
        cls   = 'change-up' if idx['up'] else 'change-down'
        arrow = '▲' if idx['up'] else '▼'
        indices_parts.append(
            f'<div class="mini-box"><span class="mini-name">{idx["name"]}</span>'
            f'<span class="mini-val">{idx["val"]}</span>'
            f'<span class="mini-pct {cls}">{arrow} {idx["pct"]}</span></div>'
        )
    indices_html = ''.join(indices_parts)

    sectors_parts = []
    for s in data['market']['sectors']:
        cls = 'change-up' if s.get('up') else 'change-down'
        sectors_parts.append(
            f'<div class="data-bar-row"><div class="data-bar-label"><span>{s["name"]}</span>'
            f'<div class="data-bar-visual"><div class="data-bar-fill" style="width:{s["val"]}; background:{s["color"]};"></div></div></div>'
            f'<span class="{cls}">{s["pct"]}</span></div>'
        )
    sectors_html = ''.join(sectors_parts)

    bigtech_parts = []
    for b in data['market']['bigtech']:
        cls = 'change-up' if b['up'] else 'change-down'
        bigtech_parts.append(
            f'<div class="mini-box" style="padding:8px 4px;"><span class="mini-name" style="font-size:0.8rem;">{b["name"]}</span>'
            f'<span class="{cls}" style="font-size:0.95rem; font-weight:700;">{b["pct"]}</span></div>'
        )
    bigtech_html = ''.join(bigtech_parts)

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

    # --- 오른쪽 카드 HTML ---
    nn = data['news']
    mk_dropdown_html = build_mk_dropdown_html(data.get('mk_data', {}))
    stock_html    = build_news_items_html(nn['fz_stock'], border='rgba(56,189,248,0.5)')
    intl_html     = build_news_items_html(nn['fz_intl'],  border='rgba(74,222,128,0.5)')

    upd_time   = nn['updated_time']
    reload_btn = (
        '<button onclick="refreshRightCard()" title="새로고침"'
        ' style="margin-left:auto;background:rgba(255,255,255,0.08);'
        'border:1px solid rgba(255,255,255,0.15);color:#94a3b8;font-size:0.8rem;'
        'padding:3px 10px;border-radius:6px;cursor:pointer;transition:all 0.2s;"'
        ' onmouseover="this.style.background=\'rgba(255,255,255,0.15)\';this.style.color=\'#f8fafc\'"'
        ' onmouseout="this.style.background=\'rgba(255,255,255,0.08)\';this.style.color=\'#94a3b8\'">⟳ 새로고침</button>'
    )

    right_card_content = (
        '<div class="news-card-header">'
        '<div class="header-top">'
        '<span class="date-badge" style="background:rgba(251,191,36,0.15);color:#fbbf24;">뉴스</span>'
        f'<span style="font-size:0.9rem;color:#94a3b8;">Updated: {upd_time} KST</span>'
        + reload_btn +
        '</div>'
        '<div class="market-status-title" style="margin-top:10px;">📰 뉴스 브리핑</div>'
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<strong style="color:#fbbf24;font-size:0.82em;display:block;margin-bottom:8px;'
        'letter-spacing:0.03em;border-bottom:1px solid rgba(251,191,36,0.2);padding-bottom:4px;">'
        '📰 매일경제</strong>'
        + mk_dropdown_html +
        '</div>'
        '<div style="margin-bottom:14px;">'
        '<strong style="color:#38bdf8;font-size:0.82em;display:block;margin-bottom:8px;'
        'letter-spacing:0.03em;border-bottom:1px solid rgba(56,189,248,0.2);padding-bottom:4px;">'
        '📈 프리진경제 주식/증권</strong>'
        + stock_html +
        '</div>'
        '<div>'
        '<strong style="color:#4ade80;font-size:0.82em;display:block;margin-bottom:8px;'
        'letter-spacing:0.03em;border-bottom:1px solid rgba(74,222,128,0.2);padding-bottom:4px;">'
        '🌐 프리진경제 국제/IT</strong>'
        + intl_html +
        '</div>'
    )

    # --- 변동성 & 매크로 카드 업데이트 ---
    if 'volatility' in data:
        vol_html = build_volatility_card_html(data['volatility'], data['news']['updated_time'])
        vol_pat  = r'<!-- VOLATILITY_CARD_START -->.*?<!-- VOLATILITY_CARD_END -->'
        vol_rep  = '<!-- VOLATILITY_CARD_START -->\n' + vol_html + '\n            <!-- VOLATILITY_CARD_END -->'
        content  = re.sub(vol_pat, vol_rep, content, flags=re.DOTALL)

    # 업데이트 로직
    pattern = r'(<!-- MARKET_NEWS_CARD_START -->)(.*?)(<!-- MARKET_NEWS_CARD_END -->)'
    if not re.search(pattern, content, re.DOTALL):
        print("마커를 찾을 수 없습니다.")
        return

    # 왼쪽 카드: 아침/저녁 업데이트 or --force 시에만 갱신
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
