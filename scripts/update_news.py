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


def get_freezine_intl_news(count=5):
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


def get_fred_history(series_id, months=24, units=None):
    """FRED 공개 CSV에서 히스토리 데이터 (API 키 불필요).
    FRED CSV URL의 units 파라미터는 무시될 수 있으므로 수동 계산:
      units='pc1': YoY 퍼센트 변화 = (현재/1년전 - 1) * 100
      units='ch1': MoM 절대 변화  = 현재 - 전월  (비농업고용 등)
      units=None : 원시값 그대로
    returns list of (YYYY-MM, float) tuples, 최근 months개월
    """
    # pc1 계산을 위해 12개월치 여분 수집
    fetch_extra = 13 if units == 'pc1' else 2 if units == 'ch1' else 0
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            content = r.read().decode('utf-8', errors='replace')
        monthly: dict = {}
        for line in content.strip().split('\n')[1:]:   # 헤더 스킵
            parts = line.strip().split(',')
            if len(parts) >= 2 and parts[1].strip() not in ('', '.'):
                try:
                    month = parts[0].strip()[:7]       # YYYY-MM
                    monthly[month] = float(parts[1].strip())
                except ValueError:
                    pass

        sorted_months = list(sorted(monthly.keys()))

        if units == 'pc1':
            # YoY 퍼센트 변화: (현재값 / 1년전값 - 1) * 100
            result: list = []
            for mo in sorted_months:
                yr_ago = f"{int(mo[:4]) - 1}{mo[4:]}"   # 1년전 동월
                if yr_ago in monthly and monthly[yr_ago] != 0:
                    yoy = (monthly[mo] / monthly[yr_ago] - 1) * 100
                    result.append((mo, float(f"{yoy:.2f}")))
            n = len(result)
            start = max(0, n - months) if months else 0
            return [result[i] for i in range(start, n)]

        elif units == 'ch1':
            # MoM 절대 변화: 현재 - 전월 (비농업고용 등 월간 순변화)
            result2: list = []
            for i in range(1, len(sorted_months)):
                mo   = sorted_months[i]
                prev = sorted_months[i - 1]
                chg  = monthly[mo] - monthly[prev]
                result2.append((mo, float(f"{chg:.2f}")))
            n2 = len(result2)
            start2 = max(0, n2 - months) if months else 0
            return [result2[i] for i in range(start2, n2)]

        else:
            # 원시값
            n = len(sorted_months)
            start = max(0, n - (months + fetch_extra)) if months else 0
            recent = [sorted_months[i] for i in range(start, n)]
            return [(mo, float(f"{monthly[mo]:.2f}")) for mo in recent]

    except Exception as e:
        print(f"[FRED history {series_id}] 실패: {e}")
        return []


# ── 경제지표 메타 (정적 정보) ──────────────────────────────────────────────────
ECON_META = {
    'fedfunds': {'label':'기준금리',      'icon':'🏦', 'unit':'%',  'freq':'FOMC',
                 'isHighGood':False, 'threshold':2.0, 'thresholdLabel':'중립금리 추정', 'color':'#3b82f6'},
    'cpi':      {'label':'CPI (YoY)',    'icon':'📈', 'unit':'%',  'freq':'월간·BLS',
                 'isHighGood':False, 'threshold':2.0, 'thresholdLabel':'Fed 목표 2%',  'color':'#ef4444'},
    'core_cpi': {'label':'코어 CPI',     'icon':'🎯', 'unit':'%',  'freq':'월간·BLS',
                 'isHighGood':False, 'threshold':2.0, 'thresholdLabel':'Fed 목표 2%',  'color':'#f97316'},
    'core_pce': {'label':'코어 PCE',     'icon':'💰', 'unit':'%',  'freq':'월간·BEA',
                 'isHighGood':False, 'threshold':2.0, 'thresholdLabel':'Fed 핵심목표', 'color':'#a855f7'},
    'payems':   {'label':'비농업 고용',  'icon':'👷', 'unit':'K',  'freq':'월간·BLS',
                 'isHighGood':True,  'threshold':100, 'thresholdLabel':'정상 수준',    'color':'#10b981'},
    'unrate':   {'label':'실업률',        'icon':'📉', 'unit':'%',  'freq':'월간·BLS',
                 'isHighGood':False, 'threshold':4.0, 'thresholdLabel':'자연실업률',   'color':'#f59e0b'},
    'dgs10':    {'label':'국채 10Y',     'icon':'🏛️', 'unit':'%',  'freq':'일간→월평균',
                 'isHighGood':None,  'threshold':4.5, 'thresholdLabel':'주의 구간',    'color':'#6366f1'},
    'spread':   {'label':'장단기 스프레드','icon':'📊','unit':'%', 'freq':'10Y-2Y',
                 'isHighGood':True,  'threshold':0,   'thresholdLabel':'역전=침체신호', 'color':'#0ea5e9'},
    'mfg_pmi':  {'label':'제조업 PMI',   'icon':'🔧', 'unit':'',   'freq':'월간·ISM',
                 'isHighGood':True,  'threshold':50,  'thresholdLabel':'50=확장기준',  'color':'#14b8a6'},
    'svc_pmi':  {'label':'서비스 PMI',   'icon':'💼', 'unit':'',   'freq':'월간·ISM',
                 'isHighGood':True,  'threshold':50,  'thresholdLabel':'50=확장기준',  'color':'#06b6d4'},
    'retail':   {'label':'소매판매 YoY', 'icon':'🛒', 'unit':'%',  'freq':'월간·Census',
                 'isHighGood':True,  'threshold':0,   'thresholdLabel':'성장 기준',    'color':'#84cc16'},
    'umcsent':  {'label':'소비자심리',   'icon':'😊', 'unit':'',   'freq':'월간·UMich',
                 'isHighGood':True,  'threshold':80,  'thresholdLabel':'낙관 기준',    'color':'#f472b6'},
}

# FRED 수집 설정 (key, series_id, units, months)
FRED_SERIES_CFG = [
    ('fedfunds', 'FEDFUNDS',  None,  24),
    ('cpi',      'CPIAUCSL',  'pc1', 24),
    ('core_cpi', 'CPILFESL',  'pc1', 24),
    ('core_pce', 'PCEPILFE',  'pc1', 24),
    ('payems',   'PAYEMS',    'ch1', 24),
    ('unrate',   'UNRATE',    None,  24),
    ('dgs10',    'DGS10',     None,  36),
    ('spread',   'T10Y2Y',    None,  36),
    ('retail',   'RSAFS',     'pc1', 24),
    ('umcsent',  'UMCSENT',   None,  24),
    # mfg_pmi / svc_pmi: ISM PMI는 FRED 미제공 → 기존 HTML 값 유지
]

ORDER_KEYS = ['fedfunds','cpi','core_cpi','core_pce','payems','unrate',
              'dgs10','spread','mfg_pmi','svc_pmi','retail','umcsent']


def generate_econ_analysis(fred_data, pmi_preserve):
    """12개 경제지표를 종합해 1문장 요약 + 2~3문장 분석 반환 (규칙 기반).
    returns dict: {summary, detail, situation, score, color}
    """
    def val(key):
        d = fred_data.get(key)
        return d['current'] if isinstance(d, dict) else None

    fed   = val('fedfunds')
    cpi   = val('cpi')
    cpce  = val('core_pce')
    unr   = val('unrate')
    dgs10 = val('dgs10')
    spr   = val('spread')
    ret   = val('retail')
    sent  = val('umcsent')
    mfg   = pmi_preserve.get('mfg_pmi', {}).get('current')
    svc   = pmi_preserve.get('svc_pmi', {}).get('current')
    if cpce is None and cpi is not None:
        cpce = cpi

    # ── 인플레이션 평가 ─────────────────────────────────────────────
    if cpi is not None:
        if cpi > 4.0:
            inf_word = f"CPI {cpi:.1f}%로 인플레이션이 심각하게 높은 수준"
            inf_fut  = "연준은 추가 긴축 또는 고금리 장기화를 선택할 가능성이 높다"
        elif cpi > 3.0:
            inf_word = f"CPI {cpi:.1f}%로 인플레이션이 여전히 높은 수준"
            inf_fut  = "금리인하 시점이 뒤로 밀릴 가능성이 크다"
        elif cpi > 2.5:
            inf_word = f"CPI {cpi:.1f}%로 인플레이션이 둔화되고 있으나 연준 목표(2%)를 상회"
            inf_fut  = "연준은 신중한 금리인하 기조를 유지할 전망이다"
        elif cpi > 1.5:
            inf_word = f"CPI {cpi:.1f}%로 인플레이션이 연준 목표(2%)에 근접"
            inf_fut  = "연준의 금리인하 여건이 성숙되고 있다"
        else:
            inf_word = f"CPI {cpi:.1f}%로 인플레이션이 목표 이하로 하락"
            inf_fut  = "연준은 경기부양을 위한 금리인하를 가속화할 수 있다"
    else:
        inf_word = "인플레이션 데이터 확인 필요"
        inf_fut  = "인플레이션 동향에 따라 통화정책 방향이 결정될 것이다"

    # ── 고용 평가 ────────────────────────────────────────────────────
    if unr is not None:
        if unr < 3.7:
            emp_word = f"실업률 {unr:.1f}%로 고용이 과열에 가까운 수준"
            emp_fut  = "임금 상승 압력이 인플레이션 재점화 위험을 높이고 있다"
        elif unr < 4.2:
            emp_word = f"실업률 {unr:.1f}%로 고용이 건강한 수준"
            emp_fut  = "소비 기반이 견조해 경기 연착륙 가능성을 높이고 있다"
        elif unr < 4.8:
            emp_word = f"실업률 {unr:.1f}%로 고용이 완만히 냉각 중"
            emp_fut  = "점진적 고용 냉각이 인플레이션 억제에 기여하고 있다"
        elif unr < 5.5:
            emp_word = f"실업률 {unr:.1f}%로 고용이 눈에 띄게 둔화"
            emp_fut  = "소비 위축 가능성이 커져 경기 하방 리스크가 증가하고 있다"
        else:
            emp_word = f"실업률 {unr:.1f}%로 고용이 크게 악화"
            emp_fut  = "경기침체 가능성이 현실화되고 있다"
    else:
        emp_word = "고용 데이터 확인 필요"
        emp_fut  = ""

    # ── 기준금리 실질 수준 평가 ──────────────────────────────────────
    if fed is not None:
        real_rate = fed - (cpi or 0)
        if real_rate > 2.0:
            rate_word = f"기준금리 {fed:.2f}%(실질금리 +{real_rate:.1f}%p)가 매우 제약적인 수준"
        elif real_rate > 0.5:
            rate_word = f"기준금리 {fed:.2f}%(실질금리 +{real_rate:.1f}%p)가 제약적인 수준"
        elif real_rate > -0.5:
            rate_word = f"기준금리 {fed:.2f}%가 중립 수준"
        else:
            rate_word = f"기준금리 {fed:.2f}%가 완화적인 수준"
    else:
        rate_word = "기준금리 데이터 확인 필요"

    # ── 장단기 스프레드 ──────────────────────────────────────────────
    if spr is not None:
        if spr < -0.5:
            curve_word = f"장단기 금리 역전({spr:.2f}%p)이 깊어 침체 선행신호를 발생"
        elif spr < 0:
            curve_word = f"장단기 금리가 소폭 역전({spr:.2f}%p)되어 경기 불확실성 반영"
        elif spr < 0.5:
            curve_word = f"장단기 스프레드(+{spr:.2f}%p)가 거의 플랫으로 경기 전환 신호"
        else:
            curve_word = f"장단기 스프레드(+{spr:.2f}%p)가 정상화되어 경기 확장 기대 반영"
    else:
        curve_word = ""

    # ── PMI 평가 ────────────────────────────────────────────────────
    pmi_parts = []
    if mfg is not None:
        if mfg < 48:   pmi_parts.append(f"제조업 PMI({mfg:.1f}) 뚜렷한 수축")
        elif mfg < 50: pmi_parts.append(f"제조업 PMI({mfg:.1f}) 위축")
        elif mfg < 52: pmi_parts.append(f"제조업 PMI({mfg:.1f}) 소폭 확장")
        else:          pmi_parts.append(f"제조업 PMI({mfg:.1f}) 견조한 확장")
    if svc is not None:
        if svc < 48:   pmi_parts.append(f"서비스 PMI({svc:.1f}) 수축")
        elif svc < 50: pmi_parts.append(f"서비스 PMI({svc:.1f}) 위축")
        elif svc < 52: pmi_parts.append(f"서비스 PMI({svc:.1f}) 완만한 확장")
        else:          pmi_parts.append(f"서비스 PMI({svc:.1f}) 강한 확장")
    pmi_word = ", ".join(pmi_parts)

    # ── 소비자심리 ───────────────────────────────────────────────────
    if sent is not None:
        if sent > 90:   sent_word = f"소비자심리({sent:.1f}) 매우 낙관적"
        elif sent > 80: sent_word = f"소비자심리({sent:.1f}) 낙관적"
        elif sent > 70: sent_word = f"소비자심리({sent:.1f}) 중립"
        elif sent > 60: sent_word = f"소비자심리({sent:.1f}) 다소 위축"
        else:           sent_word = f"소비자심리({sent:.1f}) 크게 위축"
    else:
        sent_word = ""

    # ── 종합 점수 계산 ───────────────────────────────────────────────
    score = 0.0
    if cpi is not None:
        score += 1.5 if cpi <= 2.0 else 0.5 if cpi <= 2.5 else -0.5 if cpi <= 3.5 else -1.5
    if unr is not None:
        score += 1.0 if unr < 4.0 else 0.5 if unr < 4.5 else -0.5 if unr < 5.5 else -1.5
    if mfg is not None and svc is not None:
        avg_pmi = (mfg + svc) / 2
        score += 1.0 if avg_pmi > 53 else 0.3 if avg_pmi > 51 else -0.3 if avg_pmi > 49 else -1.0
    if sent is not None:
        score += 0.5 if sent > 80 else 0.0 if sent > 65 else -0.5
    if spr is not None:
        score += 0.5 if spr > 1.0 else 0.2 if spr > 0 else -0.5 if spr > -0.5 else -1.0
    if ret is not None:
        score += 0.3 if ret > 3.0 else 0.1 if ret > 0 else -0.3

    if score > 2.5:   situation, color = "강한 확장 국면",        "#10b981"
    elif score > 1.0: situation, color = "안정적 성장 국면",       "#22c55e"
    elif score > 0:   situation, color = "완만한 성장세",          "#84cc16"
    elif score > -1.0: situation, color = "경기 불확실성 확대",     "#f59e0b"
    elif score > -2.0: situation, color = "경기 둔화 국면",        "#f97316"
    else:              situation, color = "경기 위축·침체 위험",    "#ef4444"

    # ── 1문장 요약 ───────────────────────────────────────────────────
    summary = f"{inf_word}이며, {emp_word}으로 현재 미국 경제는 '{situation}'에 위치해 있다."

    # ── 상세 분석 2~3문장 ────────────────────────────────────────────
    s1 = f"{rate_word}이며, {inf_fut}."
    parts2: list = []
    if pmi_word:     parts2.append(str(pmi_word))
    if sent_word:    parts2.append(str(sent_word))
    if curve_word:   parts2.append(str(curve_word))
    s2 = ("이며, ".join(parts2) + "이다.") if parts2 else ""

    # 전망 문장
    if score > 1.5:
        s3 = ("인플레이션 안정과 견조한 고용이 공존하는 '골디락스' 환경에 근접해 있으며, "
              "연준의 점진적 금리인하가 가시화될 경우 주식과 채권 모두 우호적인 흐름이 예상된다.")
    elif score > 0:
        if spr is not None and spr > 0:
            s3 = ("장단기 스프레드 정상화는 침체 우려가 완화되고 있음을 시사하나, "
                  "소비자심리 회복 여부와 연준의 금리 경로가 향후 3~6개월 시장 방향성을 결정하는 핵심 변수가 될 것이다.")
        else:
            s3 = ("성장 모멘텀이 유지되고 있으나 고금리 장기화에 따른 소비·부동산의 지연 효과가 "
                  "하반기 잠재적 리스크로 작용할 수 있어 선별적 투자 접근이 필요한 시점이다.")
    elif score > -1.0:
        s3 = ("불확실성이 높은 국면으로, 연준의 정책 전환(피벗) 여부와 고용지표 방향성이 시장 변동성을 좌우할 것이며, "
              "방어주·단기채권으로의 분산 투자가 유효한 전략이 될 수 있다.")
    else:
        if spr is not None and spr < 0:
            s3 = ("장단기 금리 역전은 역사적으로 6~18개월 이내 경기침체의 전조 신호로, "
                  "경기방어 자산 비중 확대와 리스크 관리가 중요하며 연준의 신속한 정책 대응 여부가 핵심 변수다.")
        else:
            s3 = ("경기 하방 압력이 가시화되고 있으며, 연준의 완화적 정책 전환과 기업 이익 전망 수정이 "
                  "시장 회복의 핵심 전제 조건으로 부각될 것이다.")

    detail = " ".join(filter(None, [s1, s2, s3]))
    return {
        'summary':   summary,
        'detail':    detail,
        'situation': situation,
        'score':     float(f"{score:.2f}"),
        'color':     color,
    }


def build_econ_dashboard_script(existing_html):
    """ECON_DATA_START/END 사이의 기존 스크립트에서 PMI 값을 보존하면서
    FRED 최신 데이터로 덮어쓴 전체 <script> 블록 반환.
    FRED 수집 실패 시 기존 HTML의 값을 그대로 유지.
    분석 문장은 월 1회만 재생성.
    """
    import re as _re
    today_str  = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    this_month = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')

    # 기존 HTML에서 PMI 값 추출 (FRED에 없으므로 보존)
    pmi_preserve = {}
    for pmi_key in ('mfg_pmi', 'svc_pmi'):
        m_cur  = _re.search(rf'{pmi_key}.*?current:([\d.\-]+)', existing_html, _re.DOTALL)
        m_prev = _re.search(rf'{pmi_key}.*?prev:([\d.\-]+)', existing_html, _re.DOTALL)
        m_chg  = _re.search(rf'{pmi_key}.*?change:([\d.\-]+)', existing_html, _re.DOTALL)
        # dates/values 배열 추출
        m_dates = _re.search(rf'{pmi_key}.*?dates:(\[.*?\])', existing_html, _re.DOTALL)
        m_vals  = _re.search(rf'{pmi_key}.*?values:(\[.*?\])', existing_html, _re.DOTALL)
        pmi_preserve[pmi_key] = {
            'current': float(m_cur.group(1))  if m_cur  else None,
            'prev':    float(m_prev.group(1)) if m_prev else None,
            'change':  float(m_chg.group(1))  if m_chg  else 0,
            'dates':   m_dates.group(1) if m_dates else '[]',
            'values':  m_vals.group(1)  if m_vals  else '[]',
        }

    # FRED 데이터 수집
    fred_data = {}
    for key, sid, units, months in FRED_SERIES_CFG:
        rows = get_fred_history(sid, months, units)
        if rows:
            dates  = [r[0] for r in rows]
            values = [r[1] for r in rows]
            current = values[-1]
            prev    = values[-2] if len(values) >= 2 else current
            change  = float(f"{current - prev:.2f}")
            fred_data[key] = {'current': current, 'prev': prev, 'change': change,
                              'dates': dates, 'values': values}
            print(f"[ECON] {key}: 현재={current} ({len(rows)}개월)")
        else:
            pass   # 실패 → 기존값 유지 (fred_data.get(key)는 None 반환)

    # 기존 HTML에서 기존값 추출 (FRED 실패 시 폴백)
    def extract_existing(key, field, default):
        pat = rf'{_re.escape(key)}.*?{field}:([\d.\-]+)'
        m = _re.search(pat, existing_html, _re.DOTALL)
        return float(m.group(1)) if m else default

    def extract_arr(key, field):
        pat = rf'{_re.escape(key)}.*?{field}:(\[.*?\])'
        m = _re.search(pat, existing_html, _re.DOTALL)
        return m.group(1) if m else '[]'

    # 각 지표별 JS 객체 생성
    ind_parts = []
    for key in ORDER_KEYS:
        meta = ECON_META.get(key, {})
        dyn  = fred_data.get(key)

        if key in ('mfg_pmi', 'svc_pmi'):
            # PMI: 기존 보존값 사용
            pp = pmi_preserve.get(key, {})
            cur_js    = str(pp['current']) if pp['current'] is not None else 'null'
            prev_js   = str(pp['prev'])    if pp['prev']    is not None else 'null'
            chg_js    = str(pp['change'])
            dates_js  = pp['dates']
            values_js = pp['values']
        elif dyn:
            cur_js    = str(dyn['current'])
            prev_js   = str(dyn['prev'])
            chg_js    = str(dyn['change'])
            dates_js  = json.dumps(dyn['dates'],  ensure_ascii=False)
            values_js = json.dumps(dyn['values'], ensure_ascii=False)
        else:
            # FRED 실패 → 기존 HTML값 유지
            cur_js    = str(extract_existing(key, 'current', 0))
            prev_js   = str(extract_existing(key, 'prev',    0))
            chg_js    = str(extract_existing(key, 'change',  0))
            dates_js  = extract_arr(key, 'dates')
            values_js = extract_arr(key, 'values')

        ihg = meta.get('isHighGood')
        ihg_js  = 'null' if ihg is None else ('true' if ihg else 'false')
        thr     = meta.get('threshold')
        thr_js  = 'null' if thr is None else str(thr)
        label   = json.dumps(meta.get('label', ''),            ensure_ascii=False)
        icon    = json.dumps(meta.get('icon',  ''),            ensure_ascii=False)
        unit    = json.dumps(meta.get('unit',  ''),            ensure_ascii=False)
        freq    = json.dumps(meta.get('freq',  ''),            ensure_ascii=False)
        thrLbl  = json.dumps(meta.get('thresholdLabel', ''),   ensure_ascii=False)
        color   = json.dumps(meta.get('color', '#3b82f6'),     ensure_ascii=False)

        ind_parts.append(
            f'    {key}: {{label:{label},icon:{icon},unit:{unit},freq:{freq},'
            f'isHighGood:{ihg_js},threshold:{thr_js},thresholdLabel:{thrLbl},color:{color},'
            f'current:{cur_js},prev:{prev_js},change:{chg_js},'
            f'dates:{dates_js},values:{values_js}}}'
        )

    # ── 월별 분석 생성 (월 1회만 재생성, 나머지는 기존 보존) ───────────
    existing_month_m = _re.search(r'analysisMonth:\s*"([^"]*)"', existing_html)
    existing_month   = existing_month_m.group(1) if existing_month_m else ''

    if existing_month == this_month:
        # 이번 달 분석 이미 생성됨 → 기존 텍스트 보존
        ex_sum = _re.search(r'analysisSummary:\s*"((?:[^"\\]|\\.)*)"', existing_html)
        ex_det = _re.search(r'analysisDetail:\s*"((?:[^"\\]|\\.)*)"', existing_html)
        ex_sit = _re.search(r'analysisSituation:\s*"([^"]*)"',         existing_html)
        ex_col = _re.search(r'analysisColor:\s*"([^"]*)"',             existing_html)
        ex_scr = _re.search(r'analysisScore:\s*([\d.\-]+)',            existing_html)
        analysis = {
            'summary':   ex_sum.group(1) if ex_sum else '',
            'detail':    ex_det.group(1) if ex_det else '',
            'situation': ex_sit.group(1) if ex_sit else '',
            'color':     ex_col.group(1) if ex_col else '#84cc16',
            'score':     float(ex_scr.group(1)) if ex_scr else 0.0,
        }
        print(f"[ECON] 분석 보존 (이미 {this_month} 생성됨)")
    else:
        # 새 달 → 새 분석 생성
        analysis = generate_econ_analysis(fred_data, pmi_preserve)
        print(f"[ECON] 신규 분석 생성: {analysis['situation']} (점수={analysis['score']})")

    # JSON 직렬화로 특수문자 안전 처리
    ana_summary   = json.dumps(analysis['summary'],   ensure_ascii=False)
    ana_detail    = json.dumps(analysis['detail'],    ensure_ascii=False)
    ana_situation = json.dumps(analysis['situation'], ensure_ascii=False)
    ana_color     = json.dumps(analysis['color'],     ensure_ascii=False)
    ana_score     = analysis['score']

    ind_block = ',\n'.join(ind_parts)
    script = (
        '<script>\n'
        'var ECON_DATA = {\n'
        f'  lastUpdated: "{today_str}",\n'
        f'  analysisMonth: "{this_month}",\n'
        f'  analysisSummary: {ana_summary},\n'
        f'  analysisDetail: {ana_detail},\n'
        f'  analysisSituation: {ana_situation},\n'
        f'  analysisColor: {ana_color},\n'
        f'  analysisScore: {ana_score},\n'
        '  indicators: {\n'
        f'{ind_block}\n'
        '  }\n'
        '};\n'
        '</script>'
    )
    return script


def update_econ_dashboard(content):
    """<!-- ECON_DATA_START -->...<!-- ECON_DATA_END --> 블록을 FRED 최신값으로 교체"""
    pattern = r'(<!-- ECON_DATA_START -->)(.*?)(<!-- ECON_DATA_END -->)'
    m = re.search(pattern, content, re.DOTALL)
    if not m:
        print("[ECON] 마커 없음 - 스킵")
        return content
    existing_block = m.group(2)
    new_script = build_econ_dashboard_script(existing_block)
    new_block = m.group(1) + '\n' + new_script + '\n            ' + m.group(3)
    updated = content[:m.start()] + new_block + content[m.end():]
    print("[ECON] 경제지표 대시보드 업데이트 완료")
    return updated


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
                        <div style="margin-top:5px;font-size:0.64rem;color:#64748b;">{pcr_date_str} CBOE / yfinance</div>
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
                        <div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);
                                    font-size:0.65rem;color:#94a3b8;line-height:2.0;">
                            📌 P/C &lt;0.7 <span style="color:#f87171;font-weight:600;">과열</span>
                            · 0.7-1.0 <span style="color:#facc15;font-weight:600;">중립</span>
                            · &gt;1.0 <span style="color:#4ade80;font-weight:600;">방어</span><br>
                            📌 VIX &lt;15 <span style="color:#4ade80;font-weight:600;">안정</span>
                            · 15-20 <span style="color:#a3e635;font-weight:600;">보통</span>
                            · 20-25 <span style="color:#facc15;font-weight:600;">주의</span>
                            · &gt;25 <span style="color:#f87171;font-weight:600;">공포</span><br>
                            📌 스프레드 양수=<span style="color:#4ade80;font-weight:600;">정상</span>
                            · 음수=<span style="color:#f87171;font-weight:600;">역전(침체신호)</span>
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

    # MK RSS 섹션별 기사 수집 (10건)
    mk_data = get_mk_rss_all_sections(10)

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
        '<div>'
        '<strong style="color:#fbbf24;font-size:0.82em;display:block;margin-bottom:8px;'
        'letter-spacing:0.03em;border-bottom:1px solid rgba(251,191,36,0.2);padding-bottom:4px;">'
        '📰 매일경제</strong>'
        + mk_dropdown_html +
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
    updated = update_econ_dashboard(updated)   # 경제지표 FRED 데이터 업데이트
    with open(INDEX_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(updated)
    print("index.html 업데이트 완료.")


if __name__ == "__main__":
    update_index_html(get_latest_market_data())
