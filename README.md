# Trading AI System Scaffold

이 저장소에는 기존 정적 페이지와 별도로, 요청하신 멀티 타임프레임 기반 트레이딩 시스템의 코어 Python 패키지인 `trading_ai_system`을 추가했습니다.

## 이번에 구현한 범위

- `MTF` 점수화와 상위/하위 프레임 정합성 보정
- 업로드 문서 원칙을 반영한 explainable rule registry
- `확인 진입`, `중첩 타겟 경계`, `분할 진입/분할 익절`, `짧은 손절`, `역추세 probe-only` 로직
- `XGBoost/LSTM/RF` soft voting 형태의 최종 예측 파이프라인
- feature catalog 80개
- LSTM용 sequence/label helper
- Streamlit 데모 대시보드
- 규칙 on/off를 비교할 수 있는 간단한 백테스트 러너

## 문서 반영 포인트

- `spd 인터뷰 매매원칙.docx`
  - 손절이 짧고 명확한 자리만 진입
  - FOMO/추격 진입 금지
  - 확인 진입
  - 분할 익절
  - 같은 봉 재진입 금지
- `spd 인터뷰 매매타점과 그래프..docx`
  - 채널 이탈/리테스트
  - 다이버전스
  - 반익/완익
  - 이벤트 변동성 경계
- `요약.docx`
  - 공통구간
  - 피보나치/파동 상태
  - 패턴 컨펌 + 거래량 동반 돌파
  - 4번째 터치 붕괴 리스크
- 사용자 정리 및 접근 가능한 문서 내용
  - 중첩 타겟 구간 보수화
  - 상위 TF 우선, 하위 TF 청산 우선
  - 모델보다 룰 엔진 우선

`PDF/HWP`는 현재 로컬 도구 제약 때문에 본문 전체 추출은 못 했지만, 사용자께서 명시한 Glenn Neely/차설 방향은 `wave`/`target_zone` feature slot과 rule hook으로 반영해 두었습니다.

## 핵심 파일

- `trading_ai_system/signals/mtf_scoring.py`
- `trading_ai_system/strategy/rule_registry.py`
- `trading_ai_system/strategy/trade_constraints.py`
- `trading_ai_system/strategy/entry_rules.py`
- `trading_ai_system/strategy/exit_rules.py`
- `trading_ai_system/strategy/risk_manager.py`
- `trading_ai_system/features/feature_catalog.py`
- `trading_ai_system/features/feature_builder.py`
- `trading_ai_system/models/predictor.py`
- `trading_ai_system/dashboard/streamlit_app.py`

## 빠른 실행

```bash
python3 -m pytest tests
streamlit run run_streamlit.py
```

## 다음 구현 권장 순서

1. `data/` 계층에 실제 loader 추가
2. indicator 계산기를 pandas 기반으로 연결
3. feature builder를 DataFrame 입력 기반으로 확장
4. XGBoost/LSTM 학습 스크립트 연결
5. 백테스트를 OHLC replay 기반으로 고도화
