const state = {
  lang: "en",
  recommendationId: null,
};

const copy = {
  en: {
    subtitle: "Ingredient-first Korean beauty recommendations for international shoppers.",
    queryTitle: "Find products",
    queryPlaceholder: "Tell us your skin type, concerns, allergies, and product category",
    limit: "Results",
    openai: "Use OpenAI explanation",
    recommend: "Recommend",
    disclaimer: "Not sponsored. Cosmetic guidance only, not medical advice.",
    sessionTitle: "Session memory",
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
    subtitle: "외국인 구매자를 위한 성분 우선 한국 뷰티 추천",
    queryTitle: "제품 찾기",
    queryPlaceholder: "피부 타입, 고민, 알레르기, 원하는 제품군을 적어주세요",
    limit: "결과 수",
    openai: "OpenAI 설명 사용",
    recommend: "추천받기",
    disclaimer: "광고가 아닙니다. 화장품 선택 보조이며 의학적 조언이 아닙니다.",
    sessionTitle: "세션 기억",
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
  document.querySelector("#recommend").addEventListener("click", () => submitRecommendation(false));
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
}

async function loadSession() {
  const response = await fetch("/api/session");
  const data = await response.json();
  document.querySelector("#sessionHash").textContent = data.session_id_hash || "New";
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
  setStatus(`${data.decision} | OpenAI: ${data.openai_status}`);
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

function renderProfile(profile) {
  const view = document.querySelector("#profileView");
  const fields = ["skin_type", "concerns", "desired_categories", "sensitivities", "allergies", "avoid_ingredients"];
  view.innerHTML = fields
    .map((field) => {
      const value = Array.isArray(profile[field]) ? profile[field].join(", ") : profile[field];
      return `<div><dt>${field.replaceAll("_", " ")}</dt><dd>${escapeHtml(value || "-")}</dd></div>`;
    })
    .join("");
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
