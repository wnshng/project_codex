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

const runSimulation = () => {
  if (runSimBtn.dataset.loading === "true") {
    return;
  }

  trackEvent("simulation_start");
  runSimBtn.dataset.loading = "true";
  runSimBtn.classList.add("opacity-80");
  simStatus.textContent = "데이터를 불러오는 중...";

  const steps = [
    {
      percent: 32,
      status: "채무 구조를 분해하고 금리를 정리하고 있습니다.",
      interest: "2,900만 원",
      cashflow: "+2.8%",
      savings: "6%",
      highlightIndex: 0,
    },
    {
      percent: 68,
      status: "현금흐름 패턴과 리스크 구간을 분석 중입니다.",
      interest: "2,520만 원",
      cashflow: "+7.4%",
      savings: "11%",
      highlightIndex: 1,
    },
    {
      percent: 100,
      status: "최적 상환 순서와 금리 인센티브가 적용되었습니다.",
      interest: "2,190만 원",
      cashflow: "+12.6%",
      savings: "18%",
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
        trackEvent("simulation_complete", {
          savings_rate: step.savings,
          cashflow_change: step.cashflow,
        });
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
        trackEvent("lead_submit_success");
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
