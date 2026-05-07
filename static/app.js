const state = {
  lang: "en",
  recommendationId: null,
  profile: {},
};

const copy = {
  en: {
    heroEyebrow: "Rule-first beauty advisor",
    heroTitle: "Ingredient-safe K-beauty recommendations",
    subtitle: "Ingredient-first Korean beauty recommendations for international shoppers.",
    ads: "ads",
    evidenceSignal: "ingredient evidence",
    guardrailSignal: "guardrailed summary",
    queryEyebrow: "Skin brief",
    queryTitle: "Find products",
    queryPlaceholder: "Tell us your skin type, concerns, allergies, and product category",
    limit: "Results",
    openai: "Use OpenAI explanation",
    recommend: "Recommend",
    disclaimer: "Not sponsored. Cosmetic guidance only, not medical advice.",
    memoryEyebrow: "Personalization",
    sessionTitle: "Session memory",
    resultEyebrow: "Recommendation board",
    resultTitle: "Matched products and rationale",
    overallFeedback: "Was this recommendation useful?",
    followUpPlaceholder: "Ask a follow-up, e.g. make it cheaper or gentler",
    askAgain: "Ask",
    loading: "Analyzing skin profile and ingredients...",
    similar: "Similar products",
    cautions: "Cautions",
    evidence: "Evidence",
    missing: "Missing data",
  },
  ko: {
    heroEyebrow: "룰 기반 뷰티 어드바이저",
    heroTitle: "성분 안전성을 먼저 보는 K-뷰티 추천",
    subtitle: "외국인 구매자를 위한 성분 우선 한국 뷰티 추천",
    ads: "광고 없음",
    evidenceSignal: "성분 근거",
    guardrailSignal: "가드레일 요약",
    queryEyebrow: "피부 브리프",
    queryTitle: "제품 찾기",
    queryPlaceholder: "피부 타입, 고민, 알레르기, 원하는 제품군을 적어주세요",
    limit: "결과 수",
    openai: "OpenAI 설명 사용",
    recommend: "추천받기",
    disclaimer: "광고가 아닙니다. 화장품 선택 보조이며 의학적 조언이 아닙니다.",
    memoryEyebrow: "개인화",
    sessionTitle: "세션 기억",
    resultEyebrow: "추천 보드",
    resultTitle: "추천 제품과 근거",
    overallFeedback: "이번 추천이 유용했나요?",
    followUpPlaceholder: "후속 질문을 해보세요. 예: 더 저렴하고 순한 제품",
    askAgain: "질문",
    loading: "피부 프로필과 성분을 분석하는 중...",
    similar: "유사 제품",
    cautions: "주의점",
    evidence: "근거",
    missing: "누락 데이터",
  },
};

const profileLabels = {
  en: {
    skin_type: "skin type",
    concerns: "concerns",
    desired_categories: "desired categories",
    preferred_ingredients: "preferred ingredients",
    sensitivities: "sensitivities",
    allergies: "allergies",
    avoid_ingredients: "avoid ingredients",
    max_price_usd: "max price",
  },
  ko: {
    skin_type: "피부 타입",
    concerns: "고민",
    desired_categories: "제품군",
    preferred_ingredients: "선호 성분",
    sensitivities: "선호/민감 신호",
    allergies: "알레르기",
    avoid_ingredients: "피해야 할 성분",
    max_price_usd: "최대 가격",
  },
};

const profileValues = {
  ko: {
    oily: "지성",
    dry: "건성",
    combination: "복합성",
    sensitive: "민감성",
    normal: "보통",
    oil_control: "유분 조절",
    acne: "여드름",
    clogged_pores: "막힌 모공",
    hydration: "수분 보습",
    barrier_support: "피부 장벽",
    redness: "붉은기 진정",
    hyperpigmentation: "잡티/색소",
    anti_aging: "탄력/주름",
    texture: "피부결",
    basic: "기초 루틴",
    cleanser: "클렌저",
    toner: "토너",
    serum: "세럼",
    moisturizer: "보습제",
    sunscreen: "선크림",
    niacinamide: "나이아신아마이드",
    "salicylic acid": "살리실산/BHA",
    "green tea extract": "녹차 추출물",
    panthenol: "판테놀",
    "ceramide np": "세라마이드 NP",
    glycerin: "글리세린",
    "hyaluronic acid": "히알루론산",
    retinol: "레티놀",
    "azelaic acid": "아젤라익애씨드",
    "centella asiatica": "병풀/시카",
    "zinc pca": "징크 PCA",
    gentle_preference: "순한 제품 선호",
    fragrance_sensitive: "향료 민감/무향 선호",
    budget_preference: "저렴한 제품 선호",
    alcohol_sensitive: "알코올 민감",
    salicylate_allergy: "살리실레이트 알레르기",
    snail_allergy: "달팽이 성분 알레르기",
    fragrance: "향료",
    parfum: "파르팜",
    "essential oil": "에센셜 오일",
  },
};

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  applyLanguage("en");
  loadSession();
  if (window.lucide) window.lucide.createIcons();
});

function bindEvents() {
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => applyLanguage(button.dataset.lang));
  });
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector("#query").value = button.dataset.prompt;
    });
  });
  document.querySelector("#recommend").addEventListener("click", () => submitRecommendation(Boolean(state.recommendationId)));
  document.querySelector("#followUpForm").addEventListener("submit", (event) => {
    event.preventDefault();
    submitRecommendation(true);
  });
  document.querySelector("#resetSession").addEventListener("click", resetSession);
  document.querySelector("#overallFeedback").addEventListener("click", (event) => {
    const button = event.target.closest("[data-feedback]");
    if (button) sendFeedback({ target: "result", feedback: button.dataset.feedback });
  });
}

function applyLanguage(lang) {
  state.lang = lang;
  document.documentElement.lang = lang === "ko" ? "ko" : "en";
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.classList.toggle("active", button.dataset.lang === lang);
  });
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = copy[lang][element.dataset.i18n] || element.textContent;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = copy[lang][element.dataset.i18nPlaceholder] || element.placeholder;
  });
  renderProfile(state.profile || {});
}

async function loadSession() {
  const response = await fetch("/api/session");
  const data = await response.json();
  document.querySelector("#sessionHash").textContent = data.session_id_hash || "New";
  state.profile = data.profile || {};
  renderProfile(data.profile || {});
}

async function submitRecommendation(isFollowUp) {
  const input = isFollowUp ? document.querySelector("#followUpQuery") : document.querySelector("#query");
  const query = input.value.trim();
  if (!query) return;
  setStatus(copy[state.lang].loading);
  const response = await fetch(isFollowUp ? "/api/follow-up" : "/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit: Number(document.querySelector("#limit").value || 3),
      use_openai: document.querySelector("#useOpenAI").checked,
      language: state.lang,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(data.detail || "Request failed");
    return;
  }
  state.recommendationId = data.recommendation_id;
  setStatus(formatStatus(data, isFollowUp));
  state.profile = data.profile || {};
  renderProfile(data.profile || {});
  renderExplanation(data);
  renderResults(data.results || []);
  document.querySelector("#overallFeedback").classList.remove("hidden");
  document.querySelector("#followUpForm").classList.remove("hidden");
  if (isFollowUp) input.value = "";
  await loadSession();
  if (window.lucide) window.lucide.createIcons();
}

function setStatus(message) {
  document.querySelector("#status").textContent = message;
}

function formatStatus(data, isFollowUp) {
  const parts = [
    isFollowUp ? (state.lang === "ko" ? "후속 질문 반영" : "Follow-up applied") : data.decision,
    `OpenAI: ${data.openai_status}`,
  ];
  const signals = summarizeProfileSignals(data.profile || {});
  if (signals) parts.push(signals);
  return parts.join(" | ");
}

function summarizeProfileSignals(profile) {
  const values = [
    profile.skin_type,
    ...(profile.concerns || []),
    ...(profile.preferred_ingredients || []),
    ...(profile.sensitivities || []),
    profile.max_price_usd ? `$${Number(profile.max_price_usd).toFixed(2)} 이하` : null,
  ]
    .filter(Boolean)
    .map(formatProfileValue);
  return [...new Set(values)].slice(0, 6).join(", ");
}

function renderProfile(profile) {
  const view = document.querySelector("#profileView");
  const fields = [
    "skin_type",
    "concerns",
    "desired_categories",
    "preferred_ingredients",
    "sensitivities",
    "allergies",
    "avoid_ingredients",
    "max_price_usd",
  ];
  view.innerHTML = fields
    .map((field) => {
      const value = Array.isArray(profile[field])
        ? profile[field].map(formatProfileValue).join(", ")
        : formatProfileValue(profile[field]);
      const label = profileLabels[state.lang]?.[field] || field.replaceAll("_", " ");
      return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "-")}</dd></div>`;
    })
    .join("");
}

function formatProfileValue(value) {
  if (!value) return "";
  if (typeof value === "number") return `$${value.toFixed(2)}`;
  return profileValues[state.lang]?.[value] || String(value).replaceAll("_", " ");
}

function renderExplanation(data) {
  const explanation = document.querySelector("#explanation");
  const text = data.grounded_explanation || data.fallback_message || "";
  explanation.innerHTML = renderReadableText(text);
}

function renderResults(results) {
  const container = document.querySelector("#results");
  container.innerHTML = results.map(renderProductCard).join("");
  container.querySelectorAll("[data-product-feedback]").forEach((button) => {
    button.addEventListener("click", () => {
      sendFeedback({
        target: "product",
        product_id: button.dataset.productId,
        feedback: button.dataset.productFeedback,
      });
    });
  });
}

function renderProductCard(item) {
  const product = item.product;
  const chips = [...(product.concerns || []), ...(item.display_matched_ingredients || item.matched_ingredients || [])]
    .slice(0, 8)
    .map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`)
    .join("");
  const cautions = item.cautions?.length
    ? `<div class="note-list cautions"><strong>${copy[state.lang].cautions}</strong>${renderBullets(item.display_cautions || item.cautions)}</div>`
    : "";
  const evidence = item.evidence?.length
    ? `<div class="note-list"><strong>${copy[state.lang].evidence}</strong>${renderBullets(item.display_evidence || item.evidence)}</div>`
    : "";
  const missing = item.missing_data?.length
    ? `<p class="muted"><strong>${copy[state.lang].missing}:</strong> ${escapeHtml((item.display_missing_data || item.missing_data).join(", "))}</p>`
    : "";
  const reasons = item.display_reasons || item.reasons || [];
  return `
    <article class="product-card">
      <div class="product-head">
        <div>
          <h3>${escapeHtml(product.name)}</h3>
          <p class="meta">${escapeHtml(product.brand)} · ${escapeHtml(product.category)} · ${price(product.price_usd)}</p>
        </div>
        <div class="score">${Number(item.score).toFixed(1)}</div>
      </div>
      <div class="chips">${chips}</div>
      ${renderBars(item.display_score_components || item.score_components || {})}
      <div class="note-list">
        <strong>${state.lang === "ko" ? "추천 이유" : "Why this fits"}</strong>
        ${renderBullets(reasons)}
      </div>
      ${evidence}
      ${cautions}
      ${missing}
      <div class="product-actions">
        <button class="icon-button" data-product-id="${product.id}" data-product-feedback="liked" title="Like"><i data-lucide="thumbs-up"></i></button>
        <button class="icon-button" data-product-id="${product.id}" data-product-feedback="disliked" title="Dislike"><i data-lucide="thumbs-down"></i></button>
      </div>
      ${renderSimilar(item.similar_products || [])}
    </article>
  `;
}

function renderBars(components) {
  const max = Math.max(1, ...Object.values(components).map((value) => Math.abs(value)));
  return `<div class="reason-bars">${Object.entries(components)
    .map(([key, value]) => {
      const width = Math.max(2, Math.round((Math.abs(value) / max) * 100));
      return `
        <div class="bar-row">
          <span>${key.replaceAll("_", " ")}</span>
          <div class="bar-track"><div class="bar-fill ${key}" style="width:${width}%"></div></div>
          <span>${Number(value).toFixed(1)}</span>
        </div>`;
    })
    .join("")}</div>`;
}

function renderReadableText(text) {
  if (!text) return "";
  const lines = String(text).split(/\n+/).map((line) => line.trimEnd());
  const html = [];
  let list = [];
  const flushList = () => {
    if (list.length) {
      html.push(`<ul>${list.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
      list = [];
    }
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      continue;
    }
    if (trimmed.startsWith("- ")) {
      list.push(trimmed.slice(2));
      continue;
    }
    flushList();
    if (/^\d+\.\s/.test(trimmed) || ["추천 제품", "Recommended options:", "리뷰 요약", "Review summary:", "추천 기준", "Guardrails:"].includes(trimmed)) {
      html.push(`<h3>${escapeHtml(trimmed)}</h3>`);
    } else {
      html.push(`<p>${escapeHtml(trimmed)}</p>`);
    }
  }
  flushList();
  return html.join("");
}

function renderBullets(items) {
  if (!items?.length) return "";
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderSimilar(products) {
  if (!products.length) return "";
  return `
    <div class="similar">
      <h3>${copy[state.lang].similar}</h3>
      <div class="similar-list">
        ${products
          .map(
            (product) => `
              <div class="similar-item">
                <strong>${escapeHtml(product.name)}</strong>
                <p class="meta">${escapeHtml(product.brand)} · ${escapeHtml(product.category)}</p>
              </div>`
          )
          .join("")}
      </div>
    </div>`;
}

async function sendFeedback(payload) {
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recommendation_id: state.recommendationId, ...payload }),
  });
  setStatus(payload.feedback === "liked" ? "Feedback saved: liked" : "Feedback saved: disliked");
}

async function resetSession() {
  await fetch("/api/session", { method: "DELETE" });
  state.recommendationId = null;
  document.querySelector("#results").innerHTML = "";
  document.querySelector("#explanation").textContent = "";
  document.querySelector("#overallFeedback").classList.add("hidden");
  document.querySelector("#followUpForm").classList.add("hidden");
  await loadSession();
  setStatus("Session reset");
}

function price(value) {
  return value == null ? "price n/a" : `$${Number(value).toFixed(2)}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
