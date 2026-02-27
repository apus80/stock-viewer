---
description: 매일 아침 자동화된 고품격 마켓 뉴스 카드 업데이트 및 배포 워크플로우
---

이 워크플로우는 매일 아침 7시(KST)에 마켓 데이터를 수집하고 시각화하여 웹사이트에 배포하는 과정을 정의합니다.

### 1단계: 마켓 데이터 수집 (Data Collection)
- **대상**: Morning Brew, Infostock, Investing.com, Finviz 등.
- **방법**: Python Scrapy 또는 BeautifulSoup을 활용하여 핵심 키워드 및 지표 수집.
- **수집 항목**:
  - 지수: Dow, S&P 500, Nasdaq 등 등락률.
  - 섹터: Magnificient 7 흐름 및 강세 섹터.
  - 심리: Fear & Greed Index 지수.

### 2단계: 데이터 정제 및 요약 (Processing & Summarization)
- **방법**: LLM(GPT-4o 등)을 활용하여 수집된 뉴스 텍스트를 카드 섹션에 적합한 데이터로 변환.
- **출력**: JSON 형식 (헤더, 대시보드 데이터, 섹터 맵 요약, 키워드).

### 3단계: 뉴스 카드 디자인 및 생성 (UI Generation)
- **방법**: 요약된 데이터를 기반으로 HTML/CSS 템플릿에 데이터 주입.
- **디자인 원칙**: 
  - 20년차 웹디자이너의 감각을 충족할 수 있는 프리미엄 레이아웃.
  - 가독성 중심의 정보 계층 구조.
  - 지수 등락에 따른 동적 컬러 및 아이콘 적용.

### 4단계: 자동 배포 (Automated Deployment)
- **방법**: GitHub Actions 워크플로우를 트리거하여 생성된 `news_card.html`을 저장소에 Push.
- **갱신**: `index.html`에서 해당 파일을 불러와 실시간 반영.

### 5단계: 관리 및 유지보수
- **로그**: 데이터 소스 연결 실패 시 알림 전송.
- **백업**: API 장애 시 최근 3일간의 데이터를 기반으로 한 백업 뉴스 표시.
