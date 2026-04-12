# Diet Tracker — 프로젝트 규칙

## 프로젝트 개요
Google OAuth 로그인 기반 개인 식단 트래커. 음식 사진 AI 분석 + 수동 추가, 일자별 기록, 캘린더·트렌드 시각화.

## 기술 스택
- **프레임워크**: Streamlit 1.42+ (st.login, st.navigation, @st.fragment)
- **AI**: Google Gemini 2.5 Flash (google-genai SDK)
- **저장소**: Google Sheets (gspread + Service Account)
- **인증**: Google OAuth (st.login)
- **차트**: Plotly go.* (plotly_dark 테마)
- **데이터**: pandas

## 디렉토리 구조
- `app.py` — 엔트리포인트 (st.navigation 라우팅)
- `config.py` — 전역 상수 (EXERCISE_TABLE, ACTIVITY_MULTIPLIERS 등)
- `services/` — 비즈니스 로직 (auth, gemini, calorie, sheets)
- `pages/` — Streamlit 페이지 (record, calendar_view, trends, profile)
- `.streamlit/` — config.toml (테마), secrets.toml (API 키)

## 실행 방법
```bash
streamlit run c:/Users/sk15y/claude/diet_calculator/app.py
```

## 사전 준비
1. Google Cloud Console: OAuth 2.0 Client ID + Service Account 생성
2. Google Sheets API + Drive API 활성화
3. `diet_tracker_db` 스프레드시트 생성 → Service Account에 편집 권한
4. `.streamlit/secrets.toml`에 키 입력

## 코딩 규칙
- 차트는 `go.*` 사용 (px 아님), PLOT_CFG 적용
- API 키는 `st.secrets`에서 읽기 (os.environ 사용 금지)
- Sheets 읽기는 `@st.cache_data(ttl=300)` 캐싱 필수
- 쓰기 후 관련 캐시 `.clear()` 호출
