# AI Smart Closet (Scaffold)

React Native(Expo) + FastAPI + Supabase + OpenAI Vision 기반의 초기 스캐폴딩입니다.

## 1) 폴더 구조

```text
.
├── backend
│   ├── app
│   │   ├── api/analyze.py
│   │   ├── main.py
│   │   ├── models/schemas.py
│   │   └── services
│   │       ├── recommend_service.py
│   │       └── vision_service.py
│   ├── sql/schema.sql
│   ├── .env.example
│   └── requirements.txt
├── mobile
│   ├── app
│   │   ├── (tabs)
│   │   │   ├── _layout.tsx
│   │   │   ├── closet.tsx
│   │   │   └── recommend.tsx
│   │   ├── _layout.tsx
│   │   ├── index.tsx
│   │   └── recommend.tsx
│   ├── src/api/client.ts
│   ├── .env.example
│   ├── babel.config.js
│   ├── package.json
│   └── tsconfig.json
└── README.md
```

## 2) 백엔드 실행

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

확인:
- `GET http://127.0.0.1:8000/health`
- `POST http://127.0.0.1:8000/api/recommend`
- `POST http://127.0.0.1:8000/api/analyze`

## 3) 모바일 실행

```bash
cd mobile
cp .env.example .env
npm install
npm run start
```

## 4) Supabase 스키마 적용

- Supabase SQL Editor에서 `backend/sql/schema.sql` 실행
- RLS 정책이 포함되어 있으므로 Auth 연동 후 테스트 권장

## 5) 환경 변수

### backend/.env
- `OPENAI_API_KEY`: OpenAI API 키
- `OPENAI_MODEL`: 기본 `gpt-4o-mini`
- `OPENAI_TIMEOUT_SECONDS`: API 타임아웃
- `OPENAI_MAX_RETRIES`: 재시도 횟수
- `CORS_ORIGINS`: 허용 Origin(쉼표 구분)

### mobile/.env
- `EXPO_PUBLIC_API_BASE_URL`: 백엔드 주소

## 6) 다음 구현 우선순위

1. 이미지 업로드(파일) FastAPI 엔드포인트 추가
2. Supabase Auth 연동 및 JWT 기반 사용자별 필터링
3. 추천 결과 저장(`outfit_recommendations`) 및 히스토리 화면
4. 테스트 코드(Pytest/Jest) 추가
