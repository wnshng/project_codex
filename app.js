lucide.createIcons();

const analyzeBtn = document.getElementById("analyzeBtn");
const analyzeSpinner = document.getElementById("analyzeSpinner");
const analyzeStatus = document.getElementById("analyzeStatus");
const currentBar = document.getElementById("currentBar");
const currentLabel = document.getElementById("currentLabel");
const aiBar = document.getElementById("aiBar");
const aiLabel = document.getElementById("aiLabel");
const resultTag = document.getElementById("resultTag");
const navCta = document.getElementById("navCta");
const heroCta = document.getElementById("heroCta");
const runSimBtn = document.getElementById("runSimBtn");
const leadCta = document.getElementById("leadCta");
const leadForm = document.getElementById("leadForm");
const leadStatus = document.getElementById("leadStatus");
const leadPage = document.getElementById("leadPage");
const leadReplyTo = document.getElementById("leadReplyTo");
const simProgress = document.getElementById("simProgress");
const simPercent = document.getElementById("simPercent");
const simSteps = document.getElementById("simSteps");
const simStatus = document.getElementById("simStatus");
const simInterest = document.getElementById("simInterest");
const simCashflow = document.getElementById("simCashflow");
const simSavings = document.getElementById("simSavings");
const simSavingsBar = document.getElementById("simSavingsBar");
const inputTotalDebt = document.getElementById("inputTotalDebt");
const inputLenders = document.getElementById("inputLenders");
const inputMaxRate = document.getElementById("inputMaxRate");
const inputMonthlyPay = document.getElementById("inputMonthlyPay");
const addDebtRow = document.getElementById("addDebtRow");
const debtRows = document.getElementById("debtRows");
const toggleDebtDetails = document.getElementById("toggleDebtDetails");
const priorityList = document.getElementById("priorityList");
const leadTotalDebt = document.getElementById("leadTotalDebt");
const leadLenders = document.getElementById("leadLenders");
const leadMaxRate = document.getElementById("leadMaxRate");
const leadMonthlyPay = document.getElementById("leadMonthlyPay");
const leadSavingsRate = document.getElementById("leadSavingsRate");
const leadCashflowChange = document.getElementById("leadCashflowChange");
const leadEstInterest = document.getElementById("leadEstInterest");
const leadDebtItems = document.getElementById("leadDebtItems");

let lastSimulation = null;

const createDebtRow = () => {
  const row = document.createElement("div");
  row.className = "grid gap-3 md:grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr_0.6fr]";
  row.innerHTML = `
    <input type="text" placeholder="금융기관" class="debt-lender rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs text-slate-100" />
    <input type="number" min="0" step="0.1" placeholder="잔액(억)" class="debt-amount rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs text-slate-100" />
    <input type="number" min="0" step="0.1" placeholder="금리(%)" class="debt-rate rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs text-slate-100" />
    <input type="number" min="0" step="1" placeholder="만기(개월)" class="debt-term rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs text-slate-100" />
    <select class="debt-type rounded-xl border border-white/10 bg-slate-900/70 px-3 py-2 text-xs text-slate-100">
      <option value="">구분</option>
      <option value="secured">담보</option>
      <option value="unsecured">신용</option>
      <option value="policy">정책</option>
    </select>
    <button type="button" class="remove-debt-row rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 md:col-span-5">
      항목 삭제
    </button>
  `;
  return row;
};

const parseDebtRows = () => {
  if (!debtRows) {
    return { items: [], totalDebt: 0, maxRate: 0, lenders: 0 };
  }

  const rows = Array.from(debtRows.children);
  const items = rows
    .map((row) => {
      const lender = row.querySelector(".debt-lender")?.value.trim() || "";
      const amount = Number(row.querySelector(".debt-amount")?.value || 0);
      const rate = Number(row.querySelector(".debt-rate")?.value || 0);
      const term = Number(row.querySelector(".debt-term")?.value || 0);
      const type = row.querySelector(".debt-type")?.value || "";
      return {
        lender,
        amount,
        rate,
        term,
        type,
      };
    })
    .filter((item) => item.amount > 0 || item.rate > 0 || item.lender);

  const totalDebt = items.reduce((sum, item) => sum + (item.amount || 0), 0);
  const maxRate = items.reduce((max, item) => Math.max(max, item.rate || 0), 0);
  const lenders = items.length;
  return { items, totalDebt, maxRate, lenders };
};

const renderPriorityList = (items) => {
  if (!priorityList) {
    return;
  }
  if (!items.length) {
    priorityList.innerHTML = `
      <div class="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-slate-300">
        상세 항목을 입력하면 추천 순서가 표시됩니다.
      </div>
    `;
    return;
  }

  const sorted = [...items].sort((a, b) => {
    if (b.rate !== a.rate) {
      return b.rate - a.rate;
    }
    return (a.term || 999) - (b.term || 999);
  });

  priorityList.innerHTML = sorted
    .map((item, idx) => {
      return `
        <div class="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-slate-200">
          <div class="flex items-center justify-between">
            <span class="text-xs text-emerald-300">${idx + 1}순위</span>
            <span class="text-xs text-slate-400">${item.type || "일반"}</span>
          </div>
          <div class="mt-2 text-sm font-semibold">${item.lender || "금융기관"}</div>
          <div class="mt-1 text-xs text-slate-400">
            잔액 ${item.amount || 0}억 · 금리 ${item.rate || 0}% · 만기 ${item.term || 0}개월
          </div>
        </div>
      `;
    })
    .join("");
};

const trackEvent = (eventName, params = {}) => {
  if (typeof window.gtag !== "function") {
    return;
  }
  window.gtag("event", eventName, params);
};

const runComparisonAnalysis = () => {
  if (analyzeBtn.dataset.loading === "true") {
    return;
  }

  trackEvent("comparison_analyze_start");
  analyzeBtn.dataset.loading = "true";
  analyzeSpinner.classList.remove("hidden");
  analyzeStatus.textContent = "AI 분석 중...";
  analyzeBtn.classList.add("opacity-80");

  setTimeout(() => {
    currentBar.style.width = "42%";
    currentLabel.textContent = "이자 42% / 원금 58%";
    aiBar.style.width = "68%";
    aiLabel.textContent = "원금 68% / 이자 32%";
    resultTag.classList.remove("hidden");
    analyzeSpinner.classList.add("hidden");
    analyzeStatus.textContent = "분석 완료 · 다시 보기";
    analyzeBtn.classList.remove("opacity-80");
    analyzeBtn.dataset.loading = "false";
    trackEvent("comparison_analyze_complete");
  }, 1400);
};

const resetSimulation = () => {
  simProgress.style.width = "0%";
  simPercent.textContent = "0%";
  simStatus.textContent = "시뮬레이션 대기 중입니다.";
  simInterest.textContent = "2,900만 원";
  simCashflow.textContent = "+0.0%";
  simSavings.textContent = "0%";
  simSavingsBar.style.width = "0%";
  Array.from(simSteps.children).forEach((item) => {
    const dot = item.querySelector("span");
    dot.className = "h-2 w-2 rounded-full bg-slate-500";
  });
};

const formatCurrency = (value) => {
  return `${value.toLocaleString("ko-KR")}만 원`;
};

const runSimulation = () => {
  if (runSimBtn.dataset.loading === "true") {
    return;
  }

  const parsed = parseDebtRows();
  const totalDebt = parsed.totalDebt > 0 ? parsed.totalDebt : Number(inputTotalDebt.value || 0);
  const lenders = parsed.lenders > 0 ? parsed.lenders : Number(inputLenders.value || 0);
  const maxRate = parsed.maxRate > 0 ? parsed.maxRate : Number(inputMaxRate.value || 0);
  const monthlyPay = Number(inputMonthlyPay.value || 0);

  if (totalDebt < 1 || totalDebt > 10000) {
    simStatus.textContent = "총 채무는 1~10,000억 범위로 입력해주세요.";
    return;
  }
  if (lenders < 1 || lenders > 50) {
    simStatus.textContent = "금융기관 수는 1~50 사이로 입력해주세요.";
    return;
  }
  if (maxRate < 1 || maxRate > 30) {
    simStatus.textContent = "최고 금리는 1~30% 범위로 입력해주세요.";
    return;
  }
  if (monthlyPay < 0.1 || monthlyPay > totalDebt) {
    simStatus.textContent = "월 상환 여력은 0.1억 이상이며 총 채무 이하여야 합니다.";
    return;
  }
  const baseInterest = Math.max(1, (totalDebt * maxRate) / 100);
  const savingsRate = Math.min(24, Math.max(8, 8 + (maxRate / 2)));
  const interestAfter = baseInterest * (1 - savingsRate / 100);
  const cashflowBoost = Math.min(18, Math.max(4, (monthlyPay / Math.max(1, totalDebt)) * 120));

  trackEvent("simulation_start", {
    total_debt: totalDebt,
    lenders,
    max_rate: maxRate,
    monthly_pay: monthlyPay,
    has_detail: parsed.items.length > 0,
  });
  runSimBtn.dataset.loading = "true";
  runSimBtn.classList.add("opacity-80");
  simStatus.textContent = "데이터를 불러오는 중...";

  const steps = [
    {
      percent: 32,
      status: "채무 구조를 분해하고 금리를 정리하고 있습니다.",
      interest: formatCurrency(baseInterest * 10000),
      cashflow: `+${(cashflowBoost * 0.4).toFixed(1)}%`,
      savings: `${Math.max(6, savingsRate * 0.5).toFixed(0)}%`,
      highlightIndex: 0,
    },
    {
      percent: 68,
      status: "현금흐름 패턴과 리스크 구간을 분석 중입니다.",
      interest: formatCurrency((baseInterest * 0.88) * 10000),
      cashflow: `+${(cashflowBoost * 0.7).toFixed(1)}%`,
      savings: `${Math.max(10, savingsRate * 0.7).toFixed(0)}%`,
      highlightIndex: 1,
    },
    {
      percent: 100,
      status: "최적 상환 순서와 금리 인센티브가 적용되었습니다.",
      interest: formatCurrency(interestAfter * 10000),
      cashflow: `+${cashflowBoost.toFixed(1)}%`,
      savings: `${savingsRate.toFixed(0)}%`,
      highlightIndex: 2,
    },
  ];

  steps.forEach((step, idx) => {
    setTimeout(() => {
      simProgress.style.width = `${step.percent}%`;
      simPercent.textContent = `${step.percent}%`;
      simStatus.textContent = step.status;
      simInterest.textContent = step.interest;
      simCashflow.textContent = step.cashflow;
      simSavings.textContent = step.savings;
      simSavingsBar.style.width = step.savings;
      Array.from(simSteps.children).forEach((item, itemIdx) => {
        const dot = item.querySelector("span");
        if (itemIdx <= step.highlightIndex) {
          dot.className = "h-2 w-2 rounded-full bg-emerald-400";
        } else {
          dot.className = "h-2 w-2 rounded-full bg-slate-500";
        }
      });

      if (idx === steps.length - 1) {
        runSimBtn.classList.remove("opacity-80");
        runSimBtn.dataset.loading = "false";
        lastSimulation = {
          totalDebt,
          lenders,
          maxRate,
          monthlyPay,
          savingsRate: Number(step.savings.replace("%", "")),
          cashflowChange: Number(step.cashflow.replace("+", "").replace("%", "")),
          estimatedInterest: step.interest,
        };
        trackEvent("simulation_complete", {
          total_debt: totalDebt,
          lenders,
          max_rate: maxRate,
          monthly_pay: monthlyPay,
          savings_rate: lastSimulation.savingsRate,
          cashflow_change: lastSimulation.cashflowChange,
          has_detail: parsed.items.length > 0,
        });
        renderPriorityList(parsed.items);
        runComparisonAnalysis();
      }
    }, 900 * (idx + 1));
  });
};

analyzeBtn.addEventListener("click", runComparisonAnalysis);
runSimBtn.addEventListener("click", () => {
  resetSimulation();
  runSimulation();
});
heroCta.addEventListener("click", () => {
  document.getElementById("simulation").scrollIntoView({ behavior: "smooth" });
  resetSimulation();
  runSimulation();
  trackEvent("hero_cta_click");
});

navCta.addEventListener("click", () => {
  trackEvent("nav_cta_click");
});

leadForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const emailInput = leadForm.querySelector("input[name='email']");
  const inputValue = emailInput ? emailInput.value.trim() : "";

  trackEvent("lead_cta_click", {
    has_value: Boolean(inputValue),
  });

  if (leadPage) {
    leadPage.value = window.location.href;
  }
  if (leadReplyTo && inputValue) {
    leadReplyTo.value = inputValue;
  }
  if (leadTotalDebt) {
    leadTotalDebt.value = inputTotalDebt.value || "";
  }
  if (leadLenders) {
    leadLenders.value = inputLenders.value || "";
  }
  if (leadMaxRate) {
    leadMaxRate.value = inputMaxRate.value || "";
  }
  if (leadMonthlyPay) {
    leadMonthlyPay.value = inputMonthlyPay.value || "";
  }
  if (lastSimulation) {
    leadSavingsRate.value = String(lastSimulation.savingsRate);
    leadCashflowChange.value = String(lastSimulation.cashflowChange);
    leadEstInterest.value = lastSimulation.estimatedInterest;
  }
  if (leadDebtItems) {
    const parsed = parseDebtRows();
    leadDebtItems.value = parsed.items.length ? JSON.stringify(parsed.items) : "";
  }

  const formData = new FormData(leadForm);
  leadCta.disabled = true;
  leadCta.classList.add("opacity-70");
  leadStatus.textContent = "전송 중입니다...";

  fetch(leadForm.action, {
    method: "POST",
    headers: {
      Accept: "application/json",
    },
    body: formData,
  })
    .then((response) => {
      if (response.ok) {
        leadStatus.textContent = "신청이 완료되었습니다. 곧 연락드리겠습니다.";
        leadForm.reset();
        trackEvent("lead_submit_success", {
          total_debt: Number(inputTotalDebt.value || 0),
          lenders: Number(inputLenders.value || 0),
          max_rate: Number(inputMaxRate.value || 0),
          monthly_pay: Number(inputMonthlyPay.value || 0),
          savings_rate: lastSimulation ? lastSimulation.savingsRate : 0,
          cashflow_change: lastSimulation ? lastSimulation.cashflowChange : 0,
        });
      } else {
        return response.json().then(() => {
          throw new Error("Submission failed");
        });
      }
    })
    .catch(() => {
      leadStatus.textContent = "전송에 실패했습니다. 잠시 후 다시 시도해주세요.";
      trackEvent("lead_submit_error");
    })
    .finally(() => {
      leadCta.disabled = false;
      leadCta.classList.remove("opacity-70");
    });
});

const revealElements = document.querySelectorAll(".reveal");
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.2 }
);

revealElements.forEach((element) => {
  observer.observe(element);
});

if (addDebtRow && debtRows) {
  addDebtRow.addEventListener("click", () => {
    debtRows.appendChild(createDebtRow());
  });
}

if (toggleDebtDetails && debtRows && addDebtRow) {
  let isOpen = false;
  toggleDebtDetails.addEventListener("click", () => {
    isOpen = !isOpen;
    debtRows.classList.toggle("hidden", !isOpen);
    addDebtRow.classList.toggle("hidden", !isOpen);
    if (isOpen && debtRows.children.length === 0) {
      debtRows.appendChild(createDebtRow());
    }
    toggleDebtDetails.innerHTML = isOpen
      ? `<span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs text-slate-300">-</span> 상세 채무 항목 접기`
      : `<span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-xs text-slate-300">+</span> 상세 채무 항목 펼치기`;
  });
}

if (debtRows) {
  debtRows.addEventListener("click", (event) => {
    const target = event.target;
    if (target && target.classList.contains("remove-debt-row")) {
      const row = target.closest("div");
      if (row) {
        row.remove();
      }
    }
  });
  debtRows.addEventListener("input", () => {
    const parsed = parseDebtRows();
    if (parsed.totalDebt > 0) {
      inputTotalDebt.value = parsed.totalDebt.toFixed(1);
    }
    if (parsed.maxRate > 0) {
      inputMaxRate.value = parsed.maxRate.toFixed(1);
    }
    if (parsed.lenders > 0) {
      inputLenders.value = String(parsed.lenders);
    }
  });
}
