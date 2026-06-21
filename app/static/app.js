/* ── Search Typeahead — Vanilla JS ────────────────────────────────────────── */
"use strict";

const searchInput    = document.getElementById("search-input");
const searchBtn      = document.getElementById("search-btn");
const suggestionList = document.getElementById("suggestion-list");
const searchResult   = document.getElementById("search-result");
const cacheBadge     = document.getElementById("cache-badge");
const trendingList   = document.getElementById("trending-list");
const refreshBtn     = document.getElementById("refresh-trending");

let debounceTimer = null;
let activeIndex   = -1;        // for keyboard navigation
let lastSuggestions = [];

// ── Debounced suggest call ──────────────────────────────────────────────────
searchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const q = searchInput.value.trim();

  if (!q) {
    closeSuggestions();
    hideBadge();
    return;
  }

  debounceTimer = setTimeout(() => fetchSuggestions(q), 300);
});

// ── Keyboard navigation ─────────────────────────────────────────────────────
searchInput.addEventListener("keydown", (e) => {
  const items = suggestionList.querySelectorAll(".suggestion-item");

  if (e.key === "ArrowDown") {
    e.preventDefault();
    activeIndex = Math.min(activeIndex + 1, items.length - 1);
    highlightItem(items);

  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    activeIndex = Math.max(activeIndex - 1, -1);
    highlightItem(items);
    if (activeIndex === -1) searchInput.value = searchInput.dataset.original || "";

  } else if (e.key === "Enter") {
    if (activeIndex >= 0 && items[activeIndex]) {
      const q = items[activeIndex].dataset.query;
      selectSuggestion(q);
    } else {
      submitSearch(searchInput.value.trim());
    }

  } else if (e.key === "Escape") {
    closeSuggestions();
  }
});

function highlightItem(items) {
  items.forEach((el, i) => el.classList.toggle("active", i === activeIndex));
  if (activeIndex >= 0 && items[activeIndex]) {
    searchInput.dataset.original = searchInput.value;
    searchInput.value = items[activeIndex].dataset.query;
  }
}

// ── Fetch suggestions from API ──────────────────────────────────────────────
async function fetchSuggestions(prefix) {
  try {
    const res  = await fetch(`/suggest?q=${encodeURIComponent(prefix)}`);
    const data = await res.json();

    lastSuggestions = data.suggestions || [];
    renderSuggestions(lastSuggestions);
    showCacheBadge(data.source, data.prefix);
  } catch (err) {
    console.error("suggest error", err);
  }
}

function renderSuggestions(suggestions) {
  suggestionList.innerHTML = "";
  activeIndex = -1;

  if (!suggestions.length) {
    closeSuggestions();
    return;
  }

  suggestions.forEach((s) => {
    const li = document.createElement("li");
    li.className = "suggestion-item";
    li.setAttribute("role", "option");
    li.dataset.query = s.query;

    const qSpan = document.createElement("span");
    qSpan.className = "suggestion-query";
    qSpan.textContent = s.query;

    const sSpan = document.createElement("span");
    sSpan.className = "suggestion-score";
    sSpan.textContent = `score ${s.score.toLocaleString()}`;

    li.appendChild(qSpan);
    li.appendChild(sSpan);

    li.addEventListener("mousedown", (e) => {
      e.preventDefault(); // prevent input blur before click fires
      selectSuggestion(s.query);
    });

    suggestionList.appendChild(li);
  });

  suggestionList.hidden = false;
}

function closeSuggestions() {
  suggestionList.hidden = true;
  suggestionList.innerHTML = "";
  activeIndex = -1;
}

// ── Select a suggestion ─────────────────────────────────────────────────────
function selectSuggestion(query) {
  searchInput.value = query;
  closeSuggestions();
  submitSearch(query);
}

// ── Submit search to POST /search ───────────────────────────────────────────
async function submitSearch(query) {
  if (!query) return;
  closeSuggestions();

  try {
    const res  = await fetch("/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();

    searchResult.textContent = `✓ "${query}" — ${data.message}`;
    searchResult.hidden = false;

    // Refresh trending after a short delay so scores can update
    setTimeout(loadTrending, 1500);
  } catch (err) {
    searchResult.textContent = "Error submitting search.";
    searchResult.hidden = false;
  }
}

searchBtn.addEventListener("click", () => submitSearch(searchInput.value.trim()));

// ── Cache badge ─────────────────────────────────────────────────────────────
function showCacheBadge(source, prefix) {
  if (source === "empty") { hideBadge(); return; }
  const isHit = source === "cache";
  cacheBadge.className = `cache-badge ${isHit ? "hit" : "miss"}`;
  cacheBadge.textContent = isHit
    ? `⚡ Cache HIT — "${prefix}" served from Redis`
    : `\u{1F4E4} Cache MISS — "${prefix}" fetched from PostgreSQL`;
  cacheBadge.hidden = false;
}

function hideBadge() { cacheBadge.hidden = true; }

// ── Trending ────────────────────────────────────────────────────────────────
async function loadTrending() {
  trendingList.innerHTML = '<span class="loading">Loading…</span>';
  try {
    const res  = await fetch("/trending?limit=15");
    const data = await res.json();

    trendingList.innerHTML = "";
    (data.trending || []).forEach((item, i) => {
      const chip = document.createElement("span");
      chip.className = "trend-chip";
      chip.innerHTML = `<span class="rank">#${i + 1}</span> ${escapeHtml(item.query)}`;
      chip.title = `Score: ${item.score} | Freq: ${item.frequency}`;
      chip.addEventListener("click", () => {
        searchInput.value = item.query;
        submitSearch(item.query);
        fetchSuggestions(item.query);
      });
      trendingList.appendChild(chip);
    });

    if (!data.trending?.length) {
      trendingList.innerHTML = '<span class="loading">No trending data yet.</span>';
    }
  } catch {
    trendingList.innerHTML = '<span class="loading">Failed to load trending.</span>';
  }
}

refreshBtn.addEventListener("click", loadTrending);

// ── Close dropdown on outside click ────────────────────────────────────────
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-container")) closeSuggestions();
});

// ── Utility ──────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Init ─────────────────────────────────────────────────────────────────────
loadTrending();
