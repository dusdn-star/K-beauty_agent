# K-beauty Agent

외국인이 한국 뷰티 제품을 고를 때 쓸 수 있는 설명 가능한 추천 agent입니다.
추천은 광고 문구나 브랜드 선호가 아니라 제품 DB의 ingredient, 피부 타입, 리뷰 신호, 근거 수준을 바탕으로 합니다.

## 핵심 원칙

- Ingredient 기반 rule-first 추천: 성분 근거가 점수에 직접 반영됩니다.
- LLM hybrid: LLM은 rule engine 결과를 자연어로 정리하는 역할만 하며, 제품/효능/리뷰를 새로 만들어내면 안 됩니다.
- Explainable recommendation: 각 제품별 점수, 추천 이유, 근거 성분, 주의점, 누락 데이터를 표시합니다.
- No ads, no brand bias: 유료/광고 신호를 사용하지 않고, 동점 또는 유사 점수에서는 브랜드 다양성을 적용합니다.
- Fallback-first: 피부 타입, 고민, 알레르기, 성분표가 부족하면 질문하거나 보수적인 fallback을 제공합니다.

## 실행

```bash
cd /home/echo/ai_security/cs146s/k-beauty-agent
python3 -m k_beauty_agent.cli "지성 피부에 맞는 기초 제품을 추천해줘"
```

## 웹앱 실행

```bash
cd /home/echo/ai_security/cs146s/k-beauty-agent
python3 -m pip install -r requirements.txt
uvicorn k_beauty_agent.web:app --reload
```

브라우저에서 `http://127.0.0.1:8000`을 열면 개인화 세션, 후속질문, liked/disliked 피드백, 유사 제품, 추천 이유 시각화를 사용할 수 있습니다.
관리자 모니터링은 `http://127.0.0.1:8000/admin`에서 `ADMIN_TOKEN`으로 접근합니다.

환경변수 예시는 `.env.example`에 있습니다. `OPENAI_API_KEY`가 없거나 API 호출이 실패하면 rule-only 설명으로 fallback합니다.

제품 DB를 바꿔 실행할 수도 있습니다.

```bash
python3 -m k_beauty_agent.cli "oily acne prone skin, fragrance-free toner" --db data/sample_products.json --limit 3
```

## 예시 동작

사용자:

```text
지성 피부에 맞는 기초 제품을 추천해줘
```

agent는 `지성`, `유분/피지`, `기초`를 감지하고 다음 기준으로 제품을 평가합니다.

- niacinamide, green tea, zinc PCA, salicylic acid 등 유분 조절 관련 근거 성분
- oily/combination skin suitability
- fragrance, salicylic allergy, pregnancy/nursing 같은 avoid 조건
- 리뷰에서 반복되는 장점/주의점
- 성분표나 리뷰 데이터 누락 여부

## Product DB 스키마

`data/sample_products.json`은 광고 편향을 피하기 위한 샘플 DB입니다. 실제 운영에서는 검증된 성분표, 출처, 수집일, 리뷰 샘플을 넣어 교체하세요.

필수 필드:

```json
{
  "id": "unique-id",
  "name": "Product name",
  "brand": "Brand name",
  "category": "toner",
  "country": "Korea",
  "ingredients": ["Water", "Niacinamide"]
}
```

권장 필드:

```json
{
  "claims": ["fragrance-free"],
  "suited_skin_types": ["oily", "combination"],
  "concerns": ["oil_control"],
  "avoid_for": ["sensitive"],
  "price_usd": 18.0,
  "rating": 4.4,
  "review_count": 1200,
  "reviews": ["Lightweight and absorbs quickly."],
  "evidence_notes": ["Verified ingredient list from official packaging."]
}
```

## 코드 구조

- `k_beauty_agent/skin.py`: 사용자 질의에서 피부 타입, 고민, 카테고리, 민감/알레르기 신호 추출
- `k_beauty_agent/database.py`: 제품 DB 로딩과 검색
- `k_beauty_agent/knowledge_base.py`: 성분별 효능, 적합 피부, 주의점, 근거 수준
- `k_beauty_agent/recommender.py`: rule-based ingredient scoring과 브랜드 다양성 정렬
- `k_beauty_agent/reviews.py`: DB 리뷰 스니펫 요약
- `k_beauty_agent/llm.py`: 선택적 LLM explainer guardrail
- `k_beauty_agent/agent.py`: 전체 agent orchestration
- `k_beauty_agent/web.py`: FastAPI 웹/API 서버
- `k_beauty_agent/storage.py`: SQLite 세션, 피드백, 로그, 모니터링 저장소
- `static/`: bilingual 웹 UI와 관리자 대시보드

## LLM hybrid 사용 방식

현재 기본 실행은 외부 API 없이 rule-based 결과를 출력합니다.
LLM을 붙일 때는 `LLMClient` 프로토콜을 구현해 `KBeautyAgent(database, llm_client=...)`에 주입하세요.

LLM은 다음을 지켜야 합니다.

- rule engine 결과에 없는 제품을 추가하지 않기
- DB에 없는 효능, 임상 결과, 리뷰를 만들지 않기
- 근거 부족, 성분표 누락, 민감성 risk를 유지하기
- promotional language 금지

## 안전한 fallback

다음 상황에서는 추천을 약하게 하거나 질문합니다.

- 피부 타입과 주요 고민이 모두 불분명함
- 제품 성분표가 없음
- 요청한 고민과 매칭되는 근거 성분이 없음
- 알레르기/임신/수유/민감성 신호와 제품 성분이 충돌함

이 agent는 화장품 선택을 돕는 도구이며 의학적 진단이나 치료를 대체하지 않습니다.
