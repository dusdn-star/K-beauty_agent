from __future__ import annotations

import re

from .knowledge_base import normalize_token
from .models import SkinProfile

SKIN_TYPE_TERMS = {
    "oily": ("oily", "oiliness", "sebum", "지성", "유분", "번들", "피지"),
    "dry": ("dry", "dehydrated", "flaky", "건성", "건조", "당김", "각질"),
    "combination": ("combination", "combo", "복합성", "t zone", "t존"),
    "sensitive": ("sensitive", "reactive", "민감", "예민", "따가움", "홍조"),
    "normal": ("normal", "보통"),
}

CONCERN_TERMS = {
    "oil_control": ("oil control", "sebum", "유분", "피지", "번들", "matte"),
    "acne": ("acne", "breakout", "pimple", "여드름", "트러블"),
    "clogged_pores": ("blackhead", "whitehead", "clogged", "블랙헤드", "화이트헤드", "모공"),
    "hydration": ("hydration", "dehydrated", "수분", "보습", "속건조"),
    "barrier_support": ("barrier", "장벽", "손상", "진정"),
    "redness": ("redness", "rosacea", "홍조", "붉", "진정"),
    "hyperpigmentation": ("dark spot", "melasma", "pigmentation", "잡티", "색소", "기미"),
    "anti_aging": ("wrinkle", "fine line", "aging", "탄력", "주름", "안티에이징"),
    "texture": ("texture", "rough", "결", "요철"),
}

CATEGORY_TERMS = {
    "cleanser": ("cleanser", "cleansing", "폼", "클렌저", "세안"),
    "toner": ("toner", "토너", "스킨"),
    "serum": ("serum", "ampoule", "essence", "세럼", "앰플", "에센스"),
    "moisturizer": ("cream", "lotion", "moisturizer", "크림", "로션", "보습제"),
    "sunscreen": ("sunscreen", "spf", "sun cream", "선크림", "자외선"),
    "basic": ("basic", "routine", "기초", "스킨케어", "루틴"),
}

SENSITIVITY_TERMS = {
    "fragrance_sensitive": ("fragrance", "perfume", "향료", "무향", "향에 민감"),
    "alcohol_sensitive": ("alcohol", "알코올"),
    "salicylate_allergy": ("aspirin allergy", "salicylate", "아스피린 알레르기"),
    "snail_allergy": ("snail allergy", "mollusk allergy", "snail", "달팽이 알레르기"),
}

GENTLE_TERMS = (
    "gentle",
    "mild",
    "soothing",
    "non-irritating",
    "non irritating",
    "순한",
    "순하게",
    "순하",
    "순한거",
    "순한 걸",
    "순한 제품",
    "저자극",
    "자극없",
    "자극 없",
    "자극 적",
    "덜 자극",
    "약산성",
)
BUDGET_TERMS = (
    "cheap",
    "cheaper",
    "budget",
    "affordable",
    "low price",
    "저렴",
    "저렴한",
    "저렴하게",
    "싼",
    "싸게",
    "더 싸",
    "싼거",
    "싼 걸",
    "가격 낮",
    "가격대 낮",
    "가격",
    "저가",
    "가성비",
    "비싸지 않",
)

INGREDIENT_TERMS = {
    "niacinamide": ("niacinamide", "나이아신아마이드", "나이아신", "비타민 b3"),
    "salicylic acid": ("salicylic acid", "bha", "betaine salicylate", "살리실산", "바하", "BHA"),
    "green tea extract": ("green tea", "green tea extract", "녹차", "녹차 추출물"),
    "panthenol": ("panthenol", "판테놀"),
    "ceramide np": ("ceramide", "ceramide np", "세라마이드"),
    "glycerin": ("glycerin", "글리세린"),
    "hyaluronic acid": ("hyaluronic acid", "sodium hyaluronate", "히알루론산", "히알루론"),
    "retinol": ("retinol", "retinal", "레티놀", "레티날"),
    "azelaic acid": ("azelaic acid", "아젤라익", "아젤라익애씨드"),
    "centella asiatica": ("centella", "centella asiatica", "cica", "병풀", "시카"),
    "zinc pca": ("zinc pca", "zinc", "징크", "아연"),
    "fragrance": ("fragrance", "parfum", "perfume", "향료", "향수"),
}


def analyze_skin_query(query: str) -> SkinProfile:
    text = query.lower()
    profile = SkinProfile()

    for skin_type, terms in SKIN_TYPE_TERMS.items():
        if _contains_any(text, terms):
            profile.skin_type = skin_type
            break

    for concern, terms in CONCERN_TERMS.items():
        if _contains_any(text, terms):
            profile.concerns.append(concern)

    for category, terms in CATEGORY_TERMS.items():
        if _contains_any(text, terms):
            profile.desired_categories.append(category)

    for sensitivity, terms in SENSITIVITY_TERMS.items():
        if _contains_any(text, terms):
            profile.sensitivities.append(sensitivity)
            if sensitivity == "fragrance_sensitive":
                profile.avoid_ingredients.extend(["fragrance", "parfum", "essential oil"])
            if sensitivity == "salicylate_allergy":
                profile.allergies.append("salicylate")
                profile.avoid_ingredients.extend(["salicylic acid", "bha"])
            if sensitivity == "snail_allergy":
                profile.allergies.append("snail_allergy")
                profile.avoid_ingredients.extend(["snail", "snail secretion filtrate"])

    if _contains_any(text, GENTLE_TERMS):
        profile.concerns.extend(["barrier_support", "redness"])
        profile.sensitivities.extend(["gentle_preference", "fragrance_sensitive"])
        profile.avoid_ingredients.extend(["fragrance", "parfum", "essential oil"])

    if _contains_any(text, BUDGET_TERMS):
        profile.sensitivities.append("budget_preference")

    profile.preferred_ingredients.extend(_extract_preferred_ingredients(text))
    profile.max_price_usd = _extract_max_price_usd(text)

    if _contains_any(text, ("pregnant", "pregnancy", "nursing", "임신", "수유")):
        profile.pregnant_or_nursing = True
        profile.avoid_ingredients.extend(["retinol", "retinal", "retinoid"])

    _infer_default_concerns(profile)

    explicit_avoids = re.findall(r"(?:avoid|without|no|빼고|제외)\s+([a-zA-Z가-힣 ]{2,30})", query)
    for item in explicit_avoids:
        cleaned = item.strip(" .,!?:;")
        if cleaned:
            profile.avoid_ingredients.append(cleaned)

    _dedupe(profile.concerns)
    _dedupe(profile.desired_categories)
    _dedupe(profile.preferred_ingredients)
    _dedupe(profile.sensitivities)
    _dedupe(profile.allergies)
    _dedupe(profile.avoid_ingredients)

    if not profile.skin_type:
        profile.uncertainty.append("skin_type")
        profile.follow_up_questions.append("What is your skin type: oily, dry, combination, sensitive, or normal?")
    if not profile.concerns:
        profile.uncertainty.append("concerns")
        profile.follow_up_questions.append("What are your top concerns: oil control, acne, hydration, redness, pigmentation, or aging?")
    if "sensitive" in (profile.skin_type or "") and not profile.avoid_ingredients:
        profile.follow_up_questions.append("Do you react to fragrance, essential oils, alcohol, acids, or retinoids?")

    return profile


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in text for term in terms)


def _extract_preferred_ingredients(text: str) -> list[str]:
    avoid_context = ("빼고", "제외", "없는", "없이", "안", "싫", "avoid", "without", "no ")
    values: list[str] = []
    for ingredient, terms in INGREDIENT_TERMS.items():
        for term in terms:
            normalized_term = normalize_token(term)
            if normalized_term not in normalize_token(text):
                continue
            window = _term_window(text, term, radius=18)
            if any(marker in window for marker in avoid_context):
                continue
            values.append(ingredient)
            break
    return values


def _extract_max_price_usd(text: str) -> float | None:
    dollar_match = re.search(r"(?:\$|usd\s*)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:달러|불|usd)", text, re.I)
    if dollar_match and _has_price_limit_context(text, dollar_match.group(0)):
        value = dollar_match.group(1) or dollar_match.group(2)
        return float(value)

    manwon_match = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원", text)
    if manwon_match and _has_price_limit_context(text, manwon_match.group(0)):
        return round(float(manwon_match.group(1)) * 10000 / 1300, 2)

    won_match = re.search(r"(\d{4,6})\s*원", text)
    if won_match and _has_price_limit_context(text, won_match.group(0)):
        return round(float(won_match.group(1)) / 1300, 2)

    return None


def _has_price_limit_context(text: str, match_text: str) -> bool:
    window = _term_window(text, match_text, radius=20)
    return any(marker in window for marker in ("이하", "미만", "아래", "under", "less", "below", "까지", "넘지"))


def _term_window(text: str, term: str, *, radius: int) -> str:
    index = normalize_token(text).find(normalize_token(term))
    if index < 0:
        index = text.find(term)
    if index < 0:
        return text
    return text[max(0, index - radius) : index + len(term) + radius]


def _dedupe(values: list[str]) -> None:
    seen: set[str] = set()
    values[:] = [item for item in values if not (item in seen or seen.add(item))]


def _infer_default_concerns(profile: SkinProfile) -> None:
    if profile.concerns or not profile.skin_type:
        return
    defaults = {
        "oily": ["oil_control"],
        "dry": ["hydration", "barrier_support"],
        "sensitive": ["redness", "barrier_support"],
        "combination": ["oil_control", "hydration"],
    }
    profile.concerns.extend(defaults.get(profile.skin_type, []))
