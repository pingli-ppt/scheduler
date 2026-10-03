const pages = [...document.querySelectorAll("[data-page]")];
const navItems = [...document.querySelectorAll("[data-nav]")];
const toast = document.querySelector("#toast");
const isDemo = new URLSearchParams(location.search).has("demo");
let toastTimer;
let scheduleRecommendations = [];
let activeRecommendation = null;
let historyItems = [];
let historyHasLoaded = false;
let activeHistoryFilter = "all";

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2600);
}

function showPage() {
  const requested = location.hash.replace("#", "") || "profile";
  let pageName = pages.some((page) => page.dataset.page === requested) ? requested : "profile";
  if (!isDemo && localStorage.getItem("guochu_child_group") === "control" && ["schedule", "report", "share"].includes(pageName)) {
    pageName = "daily";
  }
  pages.forEach((page) => { page.hidden = page.dataset.page !== pageName; });
  const activeNav = ["report", "share"].includes(pageName) ? "schedule" : pageName;
  navItems.forEach((item) => item.classList.toggle("active", item.dataset.nav === activeNav));
  window.scrollTo({ top: 0, behavior: "instant" });
  if (pageName === "schedule" && !scheduleRecommendations.length) loadSchedule();
  if (pageName === "report") renderReportFood();
  if (pageName === "history" && !historyHasLoaded) loadHistory();
  if (pageName === "share") renderShare();
}

function applyGroupVisibility() {
  const isControl = !isDemo && localStorage.getItem("guochu_child_group") === "control";
  document.querySelector(".bottom-nav").classList.toggle("control-mode", isControl);
  document.querySelector('[data-nav="schedule"]').hidden = isControl;
}

async function restoreSavedProfile() {
  const childId = localStorage.getItem("guochu_child_id");
  if (!childId || isDemo) return;
  try {
    const child = await request(`/children/${encodeURIComponent(childId)}`);
    document.querySelector("#child-id").value = child.id;
    document.querySelector("#nickname").value = child.nickname;
    document.querySelector("#birth-date").value = child.birth_date;
    document.querySelector("#weaning-start").value = child.weaning_start;
    document.querySelectorAll("#allergen-options [data-value]").forEach((button) => {
      const selected = child.known_allergens.includes(button.dataset.value);
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    document.querySelector(`input[name="group"][value="${child.group}"]`).checked = true;
    localStorage.setItem("guochu_child_nickname", child.nickname);
    localStorage.setItem("guochu_child_group", child.group);
    applyGroupVisibility();
  } catch (_) {
    // 保留空白表单，让家长可以重新建档；接口错误会在实际保存时提示。
  }
}

window.addEventListener("hashchange", showPage);

document.querySelectorAll(".choice-chip, .category-option").forEach((button) => {
  button.addEventListener("click", () => {
    button.classList.toggle("selected");
    button.setAttribute("aria-pressed", String(button.classList.contains("selected")));
    updateCategorySummary();
  });
});

function selectedValues(containerSelector) {
  return [...document.querySelectorAll(`${containerSelector} .selected`)].map((item) => item.dataset.value);
}

function updateCategorySummary() {
  const count = selectedValues("#category-options").length;
  document.querySelector("#category-count").textContent = count;
  document.querySelector("#category-progress-bar").style.width = `${(count / 7) * 100}%`;
  const message = document.querySelector("#category-message");
  if (count >= 4) message.textContent = "已达到七类中的四类";
  else if (count > 0) message.textContent = `再记录 ${4 - count} 类达到四类`;
  else message.textContent = "点选今天吃到的类别";
}

document.querySelectorAll(".stepper button").forEach((button) => {
  button.addEventListener("click", () => {
    const output = document.querySelector(`#${button.closest(".stepper").dataset.target}`);
    output.value = Math.max(0, Number(output.value) + Number(button.dataset.step));
    output.textContent = output.value;
  });
});

function apiErrorMessage(error) {
  if (error instanceof TypeError) return "暂时无法连接接口，请确认本机服务已经启动";
  return error.message || "保存失败，请稍后重试";
}

async function request(path, options) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || "请求未成功");
  return body;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00`);
  return {
    day: `${date.getMonth() + 1}/${date.getDate()}`,
    weekday: ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()],
    full: `${date.getMonth() + 1}月${date.getDate()}日`,
  };
}

function longDate(value) {
  const date = new Date(`${value}T00:00:00`);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function textureText(item) {
  if (item.texture_desc) return item.texture_desc;
  return { 1: "细腻泥糊", 2: "碎末状", 3: "软碎块", 4: "软块或指状" }[item.texture] || "按月龄处理";
}

const demoSchedule = [
  { recommendation_id: 101, date: "2026-10-07", food_id: 52, food_name: "牛肉泥", texture: 2, texture_desc: "细软碎末", reason: "近7天肉类覆盖不足，优先安排富含铁和锌的动物性食物。", source: "WS/T 678—2020《婴幼儿辅食添加营养指南》（评分-iron）" },
  { recommendation_id: 102, date: "2026-10-11", food_id: 33, food_name: "西兰花碎", texture: 2, texture_desc: "细软碎末", reason: "补充尚未覆盖的维生素A丰富蔬果类别。", source: "WS/T 678—2020《婴幼儿辅食添加营养指南》（评分-gap）" },
  { recommendation_id: 103, date: "2026-10-15", food_id: 11, food_name: "小米粥", texture: 2, texture_desc: "稠粥或软碎末", reason: "增加谷物根茎薯类的食物多样性。", source: "WS/T 678—2020《婴幼儿辅食添加营养指南》（评分-gap）" },
];

const demoHistory = [
  { food_id: 18, food_name: "香蕉泥", category: "其他蔬果", date: "2026-10-01", status: "passed" },
  { food_id: 29, food_name: "胡萝卜泥", category: "维生素A丰富蔬果", date: "2026-09-26", status: "passed" },
  { food_id: 8, food_name: "土豆泥", category: "谷物根茎薯类", date: "2026-09-22", status: "refused" },
  { food_id: 41, food_name: "鸡蛋羹", category: "蛋类", date: "2026-09-18", status: "reaction" },
];

const historyStatusText = {
  passed: "顺利通过",
  refused: "宝宝拒绝",
  reaction: "不良反应",
};

function latestHistoryByFood(items) {
  const latest = new Map();
  [...items]
    .sort((left, right) => String(left.date).localeCompare(String(right.date)))
    .forEach((item) => latest.set(Number(item.food_id), item));
  return [...latest.values()].sort((left, right) => String(right.date).localeCompare(String(left.date)));
}

function renderHistory() {
  const visible = activeHistoryFilter === "all"
    ? historyItems
    : historyItems.filter((item) => item.status === activeHistoryFilter);
  const passed = historyItems.filter((item) => item.status === "passed").length;
  const followup = historyItems.filter((item) => item.status === "refused" || item.status === "reaction").length;
  document.querySelector("#history-total").textContent = historyItems.length;
  document.querySelector("#history-passed").textContent = passed;
  document.querySelector("#history-followup").textContent = followup;
  const container = document.querySelector("#history-state");
  if (!visible.length) {
    container.innerHTML = `<div class="history-empty">${historyItems.length ? "这个分类下暂时没有记录" : "还没有新食物尝试记录。完成一次尝试后，会自动出现在这里。"}</div>`;
    return;
  }
  container.innerHTML = visible.map((item) => `<article class="card history-item ${escapeHtml(item.status)}">
    <div class="history-main"><h2>${escapeHtml(item.food_name)}</h2><p>${escapeHtml(item.category || "食物类别待补充")}</p></div>
    <div class="history-result"><b>${escapeHtml(historyStatusText[item.status] || "已记录")}</b><time datetime="${escapeHtml(item.date)}">${escapeHtml(longDate(item.date))}</time></div>
  </article>`).join("");
}

async function loadHistory() {
  const container = document.querySelector("#history-state");
  container.innerHTML = '<div class="history-loading">正在整理宝宝尝试过的食物…</div>';
  if (isDemo) {
    historyItems = latestHistoryByFood(demoHistory);
    historyHasLoaded = true;
    renderHistory();
    return;
  }
  const childId = localStorage.getItem("guochu_child_id");
  if (!childId) {
    historyHasLoaded = true;
    historyItems = [];
    renderHistory();
    return;
  }
  try {
    const [records, foods] = await Promise.all([
      request(`/children/${encodeURIComponent(childId)}/history`),
      request("/foods"),
    ]);
    const foodMap = new Map(foods.map((food) => [Number(food.id), food]));
    historyItems = latestHistoryByFood(records
      .filter((item) => item.status !== "planned")
      .map((item) => {
        const food = foodMap.get(Number(item.food_id));
        return { ...item, food_name: food?.name || `食物 #${item.food_id}`, category: food?.category || "" };
      }));
    historyHasLoaded = true;
    renderHistory();
  } catch (error) {
    container.innerHTML = `<div class="history-empty">${escapeHtml(apiErrorMessage(error))}</div>`;
  }
}

document.querySelectorAll("#history-filter [data-status]").forEach((button) => {
  button.addEventListener("click", () => {
    activeHistoryFilter = button.dataset.status;
    document.querySelectorAll("#history-filter [data-status]").forEach((item) => item.classList.toggle("selected", item === button));
    renderHistory();
  });
});

const evidenceByScore = {
  iron: {
    url: "https://www.nhc.gov.cn/fys/c100078/202502/19903ff647694f3a85ed6fe332380b34.shtml",
    title: "国家卫健委：婴幼儿营养喂养评估服务指南",
  },
  zinc: {
    url: "https://www.chinacdc.cn/jkkp/yyjk/rqyy/202408/t20240825_295588.html",
    title: "中国疾控中心：婴幼儿辅食营养素调查",
  },
  gap: {
    url: "https://www.nhc.gov.cn/fzs/c100048/202005/69a4ae35ff314ebbb34d281196a6dc87/files/1733125339160_47351.pdf",
    title: "国家卫健委：WS/T 678—2020《婴幼儿辅食添加营养指南》",
  },
  allergen_early: {
    url: "http://www.news.cn/food/20230227/67272aed87424bf0bd684c3c7f110cac/c.html",
    title: "新华网：及时引入多样化食物",
  },
};

function evidenceLink(item) {
  const score = String(item.source || "").match(/评分-([a-z_]+)/)?.[1];
  if (score && evidenceByScore[score]) return evidenceByScore[score];
  const url = String(item.source || "").match(/https?:\/\/[^\s；;）)]+/)?.[0];
  return url ? { url, title: "查看这项食物资料的原始来源" } : evidenceByScore.gap;
}

function renderSchedule() {
  const container = document.querySelector("#schedule-state");
  if (!scheduleRecommendations.length) {
    container.innerHTML = '<div class="schedule-empty">暂时没有可展示的安排，请先完善宝宝档案。</div>';
    return;
  }
  container.innerHTML = scheduleRecommendations.map((item, index) => {
    const date = shortDate(item.date);
    const evidence = evidenceLink(item);
    return `<article class="card schedule-item ${index === 0 ? "featured" : ""}">
      <div class="schedule-date"><b>${escapeHtml(date.day)}</b><span>${escapeHtml(date.weekday)}</span></div>
      <div class="schedule-food">
        <h2>${escapeHtml(item.food_name)}</h2>
        <span class="texture-badge">${escapeHtml(textureText(item))}</span>
        <div class="reason-box"><b>为什么推荐：</b>${escapeHtml(item.reason || "根据近期类别缺口和月龄安排")}</div>
        <div class="schedule-actions">
          <a class="source-link" href="${escapeHtml(evidence.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(evidence.title)}（在新页面打开）">查看依据</a>
          <button type="button" class="record-button" data-report-id="${Number(item.recommendation_id)}">记录这次尝试</button>
        </div>
      </div>
    </article>`;
  }).join("");
  container.querySelectorAll("[data-report-id]").forEach((button) => button.addEventListener("click", () => openReport(Number(button.dataset.reportId))));
}

function sharePlanItems() {
  if (scheduleRecommendations.length) return scheduleRecommendations.slice(0, 4);
  return isDemo ? demoSchedule : [];
}

function shareBabyName() {
  return localStorage.getItem("guochu_child_nickname") || document.querySelector("#nickname").value.trim() || "宝宝";
}

function buildShareText() {
  const items = sharePlanItems();
  const lines = items.map((item) => `• ${longDate(item.date)}：${item.food_name}（${textureText(item)}）`);
  return [
    `【果初】${shareBabyName()}近期辅食安排`,
    ...lines,
    "",
    "每种新食物间隔约4天；首次尝试请少量提供并注意观察。",
  ].join("\n");
}

function renderShare() {
  const items = sharePlanItems();
  document.querySelector("#share-baby-name").textContent = `${shareBabyName()}近期可以尝试`;
  document.querySelector("#share-generated-date").textContent = `${longDate(localDate)}整理`;
  document.querySelector("#share-schedule-list").innerHTML = items.length
    ? items.map((item) => `<div class="share-schedule-item"><time datetime="${escapeHtml(item.date)}">${escapeHtml(shortDate(item.date).full)}</time><b>${escapeHtml(item.food_name)} · ${escapeHtml(textureText(item))}</b></div>`).join("")
    : '<div class="share-schedule-item"><b>暂时没有可以分享的安排</b></div>';
}

async function copyShareText() {
  const value = buildShareText();
  try {
    await navigator.clipboard.writeText(value);
  } catch (_) {
    const input = document.createElement("textarea");
    input.value = value;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
  showToast("安排文字已复制，可以粘贴到微信");
}

document.querySelector("#open-share").addEventListener("click", () => { location.hash = "share"; });
document.querySelector("#copy-plan").addEventListener("click", copyShareText);
if (!navigator.share) {
  document.querySelector("#share-support-note").textContent = "当前本地预览不能打开系统分享；正式使用 HTTPS 部署后即可。现在可以复制文字到微信。";
}
document.querySelector("#share-plan").addEventListener("click", async () => {
  if (!sharePlanItems().length) { showToast("暂时没有可以分享的安排"); return; }
  if (navigator.share) {
    try {
      await navigator.share({ title: "果初辅食安排", text: buildShareText() });
      return;
    } catch (error) {
      if (error.name === "AbortError") return;
    }
  }
  showToast("当前预览不支持系统分享，请使用复制安排文字");
});

async function loadSchedule(force = false) {
  const container = document.querySelector("#schedule-state");
  container.innerHTML = '<div class="schedule-loading">正在整理适合宝宝的食物…</div>';
  if (isDemo) {
    scheduleRecommendations = demoSchedule;
    renderSchedule();
    if (force) showToast("刷新成功");
    return;
  }
  const childId = localStorage.getItem("guochu_child_id");
  if (!childId) {
    container.innerHTML = '<div class="schedule-empty">请先在“宝宝”页面保存档案，再生成安排。</div>';
    return;
  }
  try {
    const result = await request(`/children/${encodeURIComponent(childId)}/schedule`, {
      method: "POST",
      body: JSON.stringify({ weeks: 6, today: null }),
    });
    scheduleRecommendations = result.recommendations || [];
    renderSchedule();
    if (force) showToast("刷新成功");
  } catch (error) {
    container.innerHTML = `<div class="schedule-empty">${escapeHtml(apiErrorMessage(error))}</div>`;
  }
}

function openReport(recommendationId) {
  activeRecommendation = scheduleRecommendations.find((item) => Number(item.recommendation_id) === recommendationId) || null;
  if (!activeRecommendation) { showToast("没有找到这条推荐"); return; }
  location.hash = "report";
}

function renderReportFood() {
  const item = activeRecommendation || scheduleRecommendations[0] || demoSchedule[0];
  activeRecommendation = item;
  const date = shortDate(item.date);
  document.querySelector("#report-food-card").innerHTML = `
    <span class="food-date">${escapeHtml(date.full)}</span>
    <div><h2>${escapeHtml(item.food_name)}</h2><p>${escapeHtml(textureText(item))} · 推荐编号 #${Number(item.recommendation_id)}</p></div>`;
  document.querySelector("#outcome-date").value = item.date;
}

document.querySelector("#refresh-schedule").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  if (button.classList.contains("is-refreshing")) return;
  button.classList.add("is-refreshing");
  button.setAttribute("aria-busy", "true");
  await loadSchedule(true);
  setTimeout(() => {
    button.classList.remove("is-refreshing");
    button.removeAttribute("aria-busy");
  }, 450);
});
document.querySelectorAll("[data-back='schedule']").forEach((button) => button.addEventListener("click", () => { location.hash = "schedule"; }));

document.querySelectorAll('input[name="adopted"]').forEach((input) => input.addEventListener("change", () => {
  const adopted = document.querySelector('input[name="adopted"]:checked').value === "true";
  document.querySelector("#consumed-fieldset").hidden = !adopted;
  document.querySelector("#outcome-card").hidden = !adopted;
}));

document.querySelectorAll('input[name="outcome"]').forEach((input) => input.addEventListener("change", () => {
  const value = document.querySelector('input[name="outcome"]:checked').value;
  document.querySelector("#reaction-warning").hidden = value !== "reaction";
  const consumedValue = value === "refused" ? "false" : "true";
  document.querySelector(`input[name="consumed"][value="${consumedValue}"]`).checked = true;
}));

document.querySelectorAll('input[name="consumed"]').forEach((input) => input.addEventListener("change", () => {
  const consumed = document.querySelector('input[name="consumed"]:checked').value === "true";
  const currentOutcome = document.querySelector('input[name="outcome"]:checked').value;
  if (!consumed) document.querySelector('input[name="outcome"][value="refused"]').checked = true;
  else if (currentOutcome === "refused") document.querySelector('input[name="outcome"][value="passed"]').checked = true;
  document.querySelector("#reaction-warning").hidden = true;
}));

document.querySelector("#report-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activeRecommendation) { showToast("请先选择一条推荐"); return; }
  const adopted = document.querySelector('input[name="adopted"]:checked').value === "true";
  const consumed = adopted && document.querySelector('input[name="consumed"]:checked').value === "true";
  if (isDemo) {
    showToast(adopted ? "本次情况已记录（页面预览）" : "已记录为没有采纳（页面预览）");
    setTimeout(() => { location.hash = "schedule"; }, 700);
    return;
  }
  try {
    const id = Number(activeRecommendation.recommendation_id);
    await request(`/recommendations/${id}/engagement`, {
      method: "PATCH",
      body: JSON.stringify({ adopted, consumed }),
    });
    if (adopted) {
      const selectedOutcome = document.querySelector('input[name="outcome"]:checked').value;
      const outcome = consumed ? selectedOutcome : "refused";
      await request(`/recommendations/${id}/outcome`, {
        method: "POST",
        body: JSON.stringify({ date: document.querySelector("#outcome-date").value, status: outcome, note: document.querySelector("#outcome-note").value.trim() || null }),
      });
      showToast(outcome === "reaction" ? "已记录，并重新安排后续计划" : "本次尝试结果已保存");
    } else showToast("已记录为没有采纳");
    scheduleRecommendations = [];
    historyHasLoaded = false;
    setTimeout(() => { location.hash = "schedule"; }, 700);
  } catch (error) { showToast(apiErrorMessage(error)); }
});

document.querySelector("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const childId = String(form.get("child_id")).trim();
  const body = {
    nickname: String(form.get("nickname")).trim(),
    birth_date: form.get("birth_date"),
    weaning_start: form.get("weaning_start"),
    known_allergens: selectedValues("#allergen-options"),
    group: form.get("group"),
  };
  if (isDemo) {
    showToast("宝宝档案已保存（页面预览）");
    return;
  }
  try {
    await request(`/children/${encodeURIComponent(childId)}`, { method: "PUT", body: JSON.stringify(body) });
    localStorage.setItem("guochu_child_id", childId);
    localStorage.setItem("guochu_child_nickname", body.nickname);
    localStorage.setItem("guochu_child_group", body.group);
    scheduleRecommendations = [];
    historyHasLoaded = false;
    applyGroupVisibility();
    showToast("宝宝档案已保存");
    if (body.group === "control") setTimeout(() => { location.hash = "daily"; }, 500);
  } catch (error) { showToast(apiErrorMessage(error)); }
});

document.querySelector("#daily-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const childId = localStorage.getItem("guochu_child_id") || document.querySelector("#child-id").value.trim();
  if (!childId) { showToast("请先在“宝宝”页面保存档案"); return; }
  const body = {
    date: document.querySelector("#intake-date").value,
    categories: selectedValues("#category-options"),
    meal_count: Number(document.querySelector("#meal-count").value),
    is_breastfed: document.querySelector("#is-breastfed").checked,
    milk_feeds: Number(document.querySelector("#milk-feeds").value),
  };
  if (isDemo) {
    showToast("今天的膳食记录已保存（页面预览）");
    return;
  }
  try {
    await request(`/children/${encodeURIComponent(childId)}/daily-intake`, { method: "PUT", body: JSON.stringify(body) });
    showToast("今天的膳食记录已保存");
  } catch (error) { showToast(apiErrorMessage(error)); }
});

const today = new Date();
const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
document.querySelector("#intake-date").value = localDate;
document.querySelector("#outcome-date").value = localDate;

if (isDemo) {
  document.querySelector("#child-id").value = "GC-008";
  document.querySelector("#nickname").value = "小满";
  document.querySelector("#birth-date").value = "2026-02-18";
  document.querySelector("#weaning-start").value = "2026-08-18";
  document.querySelector('[data-value="蛋类"]').click();
  ["谷物根茎薯类", "肉类", "维生素A丰富蔬果"].forEach((value) => {
    document.querySelector(`#category-options [data-value="${value}"]`).click();
  });
} else restoreSavedProfile();

applyGroupVisibility();
showPage();
