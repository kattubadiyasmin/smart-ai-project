/**
 * Smart Study AI Companion - Client Application Logic
 * "Study smarter. Understand better. Learn faster."
 */

document.addEventListener("DOMContentLoaded", () => {
  initMobileMenu();
  initAlertDismissal();
  initDropzone();
  initDeleteModals();
  initStudyWorkspace();
});

// -----------------------------------------------------------------------------
// Safe API Fetch Wrapper (Prevents HTML "Unexpected token <" JSON parsing bugs)
// -----------------------------------------------------------------------------
async function safeApiFetch(url, options = {}) {
  const defaultHeaders = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
  };

  options.headers = {
    ...defaultHeaders,
    ...(options.headers || {}),
  };

  options.credentials = "same-origin";

  let response;
  try {
    response = await fetch(url, options);
  } catch (netErr) {
    throw new Error(`Network connection error: ${netErr.message || "Failed to reach server"}. Please verify your connection.`);
  }

  // Handle session expiration or unauthorized redirect
  if (response.status === 401 || (response.redirected && response.url.includes("/login"))) {
    window.location.href = "/login";
    throw new Error("Your session has expired. Redirecting to login page...");
  }

  // Check content type to ensure we NEVER parse HTML error pages as JSON
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    const rawText = await response.text();
    if (rawText.includes("<!DOCTYPE") || rawText.includes("<html") || rawText.includes("<!doctype")) {
      throw new Error(`Server returned an unexpected page (${response.status}). Please refresh and try again.`);
    }
    throw new Error(`Unexpected server response format (${response.status}).`);
  }

  let data;
  try {
    data = await response.json();
  } catch (jsonErr) {
    throw new Error("Invalid response format received from server. Please try again.");
  }

  if (!response.ok || data.success === false) {
    throw new Error(data.error || `Request failed with status ${response.status}`);
  }

  return data;
}

// -----------------------------------------------------------------------------
// 1. Navbar & Mobile Menu
// -----------------------------------------------------------------------------
function initMobileMenu() {
  const toggle = document.querySelector(".mobile-menu-toggle");
  const navLinks = document.querySelector(".nav-links");
  if (toggle && navLinks) {
    toggle.addEventListener("click", () => {
      navLinks.classList.toggle("mobile-open");
    });
  }
}

// -----------------------------------------------------------------------------
// 2. Alert Dismissal
// -----------------------------------------------------------------------------
function initAlertDismissal() {
  document.querySelectorAll(".alert-close").forEach((btn) => {
    btn.addEventListener("click", () => {
      const alert = btn.closest(".alert");
      if (alert) {
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-5px)";
        setTimeout(() => alert.remove(), 200);
      }
    });
  });
}

// -----------------------------------------------------------------------------
// 3. Drag & Drop PDF Upload
// -----------------------------------------------------------------------------
function initDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("pdfFileInput");
  if (!dropzone || !fileInput) return;

  const progressContainer = document.getElementById("uploadProgress");
  const progressFill = document.getElementById("progressBarFill");
  const uploadStatus = document.getElementById("uploadStatusText");
  const dropzoneContent = document.getElementById("dropzoneContent");

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  dropzone.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });

  async function handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Invalid file format. Please upload a PDF (.pdf) document.");
      return;
    }

    if (file.size > 16 * 1024 * 1024) {
      alert("File is too large. Maximum allowed size is 16 MB.");
      return;
    }

    // Show Progress State
    if (dropzoneContent) dropzoneContent.style.opacity = "0.4";
    if (progressContainer) progressContainer.style.display = "block";
    if (uploadStatus) uploadStatus.textContent = `Processing "${file.name}"... Extracting text with PyPDF2...`;
    if (progressFill) progressFill.style.width = "40%";

    const formData = new FormData();
    formData.append("file", file);

    try {
      const data = await safeApiFetch("/upload", {
        method: "POST",
        body: formData,
      });

      if (progressFill) progressFill.style.width = "100%";
      if (uploadStatus) uploadStatus.textContent = "Processing complete! Redirecting to study workspace...";
      setTimeout(() => {
        window.location.href = data.redirect_url;
      }, 500);

    } catch (error) {
      alert(error.message || "Failed to process PDF.");
      if (dropzoneContent) dropzoneContent.style.opacity = "1";
      if (progressContainer) progressContainer.style.display = "none";
      fileInput.value = "";
    }
  }
}

// -----------------------------------------------------------------------------
// 4. Delete Confirmation Modals
// -----------------------------------------------------------------------------
function initDeleteModals() {
  const modal = document.getElementById("deleteModal");
  const modalTitle = document.getElementById("deleteModalDocName");
  const deleteForm = document.getElementById("deleteDocForm");
  const cancelBtn = document.getElementById("cancelDeleteBtn");

  if (!modal) return;

  document.querySelectorAll(".btn-trigger-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const docId = btn.dataset.docId;
      const docName = btn.dataset.docName;
      if (modalTitle) modalTitle.textContent = docName;
      if (deleteForm) deleteForm.action = `/materials/delete/${docId}`;
      modal.classList.add("active");
    });
  });

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      modal.classList.remove("active");
    });
  }

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.remove("active");
    }
  });
}

// -----------------------------------------------------------------------------
// 5. Study Workspace (Summary, Questions, Flashcards, Quiz, Chat)
// -----------------------------------------------------------------------------
function initStudyWorkspace() {
  const workspaceEl = document.getElementById("studyWorkspace");
  if (!workspaceEl) return;

  const docId = workspaceEl.dataset.docId;
  if (!docId) return;

  // Initialize Essential Student Tools
  initPomodoroTimer();
  initDocumentSearch();

  // Tabs Switching
  const tabs = document.querySelectorAll(".workspace-tab");
  const panes = document.querySelectorAll(".tab-pane");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      tabs.forEach((t) => t.classList.remove("active"));
      panes.forEach((p) => p.classList.remove("active"));

      tab.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      // Auto-trigger load if tab content empty
      if (targetId === "summaryPane") loadSummary(docId, false);
      if (targetId === "questionsPane") loadQuestions(docId, false);
      if (targetId === "flashcardsPane") loadFlashcards(docId, false);
      if (targetId === "quizPane") loadQuiz(docId, false);
      if (targetId === "chatPane") initChat(docId);
    });
  });

  // Overview quick action jump buttons
  document.querySelectorAll(".quick-jump-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTabName = btn.dataset.targetTab;
      const matchingTab = document.querySelector(`.workspace-tab[data-tab="${targetTabName}"]`);
      if (matchingTab) matchingTab.click();
    });
  });

  // Regenerate button event listeners
  const regenSummaryBtn = document.getElementById("regenSummaryBtn");
  if (regenSummaryBtn) {
    regenSummaryBtn.addEventListener("click", () => loadSummary(docId, true));
  }

  const regenQuestionsBtn = document.getElementById("regenQuestionsBtn");
  if (regenQuestionsBtn) {
    regenQuestionsBtn.addEventListener("click", () => loadQuestions(docId, true));
  }

  const regenFlashcardsBtn = document.getElementById("regenFlashcardsBtn");
  if (regenFlashcardsBtn) {
    regenFlashcardsBtn.addEventListener("click", () => loadFlashcards(docId, true));
  }

  const regenQuizBtn = document.getElementById("regenQuizBtn");
  if (regenQuizBtn) {
    regenQuizBtn.addEventListener("click", () => loadQuiz(docId, true));
  }

  // Copy buttons
  setupCopyButton("copySummaryBtn", () => {
    const el = document.getElementById("summaryContentWrapper");
    return el ? el.innerText : "";
  });

  setupCopyButton("copyQuestionsBtn", () => {
    const el = document.getElementById("questionsListWrapper");
    return el ? el.innerText : "";
  });
}

function setupCopyButton(btnId, getTextFn) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.addEventListener("click", () => {
    const text = getTextFn();
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      const originalHTML = btn.innerHTML;
      btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;
      setTimeout(() => {
        btn.innerHTML = originalHTML;
      }, 2000);
    });
  });
}

// -----------------------------------------------------------------------------
// ESSENTIAL TOOL 1: POMODORO FOCUS TIMER
// -----------------------------------------------------------------------------
function initPomodoroTimer() {
  const toggleBtn = document.getElementById("togglePomodoroBtn");
  const widget = document.getElementById("pomodoroWidget");
  const display = document.getElementById("pomoTimeDisplay");
  const startBtn = document.getElementById("pomoStartBtn");
  const startText = document.getElementById("pomoStartBtnText");
  const resetBtn = document.getElementById("pomoResetBtn");
  const streakBadge = document.getElementById("pomoSessionStreak");
  const headerBadge = document.getElementById("pomodoroHeaderBadge");

  if (!toggleBtn || !widget || !display) return;

  const modeDurations = {
    focus: 25 * 60,
    shortBreak: 5 * 60,
    longBreak: 15 * 60,
  };

  let currentMode = "focus";
  let timeLeft = modeDurations[currentMode];
  let timerInterval = null;
  let isRunning = false;
  let sessionsCompleted = 0;

  toggleBtn.onclick = () => {
    const isHidden = widget.style.display === "none";
    widget.style.display = isHidden ? "block" : "none";
  };

  document.querySelectorAll(".pomodoro-mode-btn").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll(".pomodoro-mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = btn.dataset.pomoMode;
      resetTimer();
    };
  });

  function updateDisplay() {
    const mins = Math.floor(timeLeft / 60);
    const secs = timeLeft % 60;
    const timeStr = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    if (display) display.textContent = timeStr;
    if (headerBadge) {
      headerBadge.textContent = isRunning ? `⏱️ ${timeStr}` : "Focus Timer";
    }
  }

  function playChime() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.8);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.85);
    } catch (e) {
      // Audio fallback silent
    }
  }

  function startTimer() {
    if (isRunning) return;
    isRunning = true;
    if (startText) startText.textContent = "Pause";
    timerInterval = setInterval(() => {
      if (timeLeft > 0) {
        timeLeft--;
        updateDisplay();
      } else {
        clearInterval(timerInterval);
        isRunning = false;
        playChime();
        if (currentMode === "focus") {
          sessionsCompleted++;
          if (streakBadge) streakBadge.textContent = `🔥 Session ${sessionsCompleted + 1}`;
          alert("🎉 Focus session completed! Time to take a short break.");
        } else {
          alert("☕ Break finished! Ready to focus again?");
        }
        resetTimer();
      }
    }, 1000);
  }

  function pauseTimer() {
    if (!isRunning) return;
    clearInterval(timerInterval);
    isRunning = false;
    if (startText) startText.textContent = "Resume";
  }

  function resetTimer() {
    clearInterval(timerInterval);
    isRunning = false;
    timeLeft = modeDurations[currentMode];
    if (startText) startText.textContent = "Start";
    updateDisplay();
  }

  if (startBtn) {
    startBtn.onclick = () => {
      if (isRunning) pauseTimer();
      else startTimer();
    };
  }

  if (resetBtn) {
    resetBtn.onclick = resetTimer;
  }

  updateDisplay();
}

// -----------------------------------------------------------------------------
// ESSENTIAL TOOL 2: DOCUMENT SEARCH & READER
// -----------------------------------------------------------------------------
function initDocumentSearch() {
  const searchInput = document.getElementById("docSearchInput");
  const resultsDiv = document.getElementById("docSearchResults");
  const toggleRawBtn = document.getElementById("toggleRawTextBtn");
  const rawViewer = document.getElementById("rawDocViewer");

  if (toggleRawBtn && rawViewer) {
    toggleRawBtn.onclick = () => {
      const isHidden = rawViewer.style.display === "none";
      rawViewer.style.display = isHidden ? "block" : "none";
      toggleRawBtn.textContent = isHidden ? "📖 Hide Source Notes" : "📖 View Source Notes";
    };
  }

  if (!searchInput || !resultsDiv) return;

  const rawText = rawViewer ? rawViewer.innerText : "";
  const sentences = rawText
    .split(/(?<=[.!?])\s+|\n{2,}/)
    .map((s) => s.trim())
    .filter((s) => s.length > 25);

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim().toLowerCase();
    if (query.length < 2) {
      resultsDiv.style.display = "none";
      resultsDiv.innerHTML = "";
      return;
    }

    const matches = sentences.filter((s) => s.toLowerCase().includes(query)).slice(0, 6);

    if (matches.length === 0) {
      resultsDiv.style.display = "block";
      resultsDiv.innerHTML = `<p style="font-size: 0.8125rem; color: var(--text-muted); margin: 0;">No matching notes found for "${escapeHtml(query)}".</p>`;
      return;
    }

    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    let html = `<div style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.5rem;">Found ${matches.length} snippets:</div>`;

    matches.forEach((sentence) => {
      const highlighted = escapeHtml(sentence).replace(regex, `<mark style="background: #FEF08A; padding: 1px 3px; border-radius: 2px;">$1</mark>`);
      html += `
        <div style="padding: 0.5rem 0.65rem; margin-bottom: 0.35rem; background: #FFFFFF; border-radius: var(--radius-sm); font-size: 0.85rem; border: 1px solid var(--border-light); line-height: 1.5;">
          ${highlighted}
        </div>
      `;
    });

    resultsDiv.style.display = "block";
    resultsDiv.innerHTML = html;
  });
}

// -----------------------------------------------------------------------------
// SUMMARY MODULE
// -----------------------------------------------------------------------------
let summaryLoaded = false;
async function loadSummary(docId, forceRegen = false) {
  if (summaryLoaded && !forceRegen) return;

  const contentDiv = document.getElementById("summaryContentWrapper");
  const loadingDiv = document.getElementById("summaryLoadingWrapper");
  const regenBtn = document.getElementById("regenSummaryBtn");

  if (contentDiv) contentDiv.style.display = "none";
  if (loadingDiv) loadingDiv.style.display = "block";
  if (regenBtn) regenBtn.disabled = true;

  try {
    const res = await safeApiFetch(`/api/content/summary/${docId}${forceRegen ? "?regenerate=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    renderSummaryUI(res.data);
    summaryLoaded = true;
  } catch (err) {
    if (contentDiv) {
      contentDiv.innerHTML = `
        <div class="retry-error-card">
          <h3>⚠️ Notice on AI Generation</h3>
          <p>${escapeHtml(err.message)}</p>
          <button class="btn btn-primary btn-sm" onclick="loadSummary(${docId}, true)">🔄 Try Again</button>
        </div>
      `;
      contentDiv.style.display = "block";
    }
  } finally {
    if (loadingDiv) loadingDiv.style.display = "none";
    if (contentDiv) contentDiv.style.display = "block";
    if (regenBtn) regenBtn.disabled = false;
  }
}

function renderSummaryUI(data) {
  const wrapper = document.getElementById("summaryContentWrapper");
  if (!wrapper) return;

  let html = "";

  // 1. Overview
  if (data.overview) {
    html += `
      <div class="summary-section-card">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
          1. Overview
        </h3>
        <p style="color: var(--text-secondary); line-height: 1.65;">${escapeHtml(data.overview)}</p>
      </div>
    `;
  }

  // 2. Key Concepts
  if (data.key_concepts && data.key_concepts.length > 0) {
    html += `
      <div class="summary-section-card">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          2. Key Concepts
        </h3>
        <div>
          ${data.key_concepts
            .map((c) => {
              const title = typeof c === "object" ? c.title : c;
              const desc = typeof c === "object" ? c.description : "";
              return `
              <div class="concept-badge-item">
                <strong>${escapeHtml(title)}</strong>
                ${desc ? `<span style="color: var(--text-secondary);">${escapeHtml(desc)}</span>` : ""}
              </div>
            `;
            })
            .join("")}
        </div>
      </div>
    `;
  }

  // 3. Important Points
  if (data.important_points && data.important_points.length > 0) {
    html += `
      <div class="summary-section-card">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          3. Important Points
        </h3>
        <ul style="list-style-type: none; padding-left: 0;">
          ${data.important_points
            .map(
              (pt) => `
            <li style="display: flex; gap: 0.5rem; margin-bottom: 0.6rem; color: var(--text-secondary);">
              <span style="color: var(--accent-primary); font-weight: bold;">•</span>
              <span>${escapeHtml(pt)}</span>
            </li>
          `
            )
            .join("")}
        </ul>
      </div>
    `;
  }

  // 4. Exam-Focused Points
  if (data.exam_focused_points && data.exam_focused_points.length > 0) {
    html += `
      <div class="summary-section-card">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
          4. Exam-Focused Points
        </h3>
        <div>
          ${data.exam_focused_points
            .map(
              (ep) => `
            <div class="exam-point-item">
              <strong>High Yield:</strong> ${escapeHtml(ep)}
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  // 5. Short Revision Notes
  if (data.revision_notes && data.revision_notes.length > 0) {
    html += `
      <div class="summary-section-card">
        <h3>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
          5. Short Revision Notes
        </h3>
        <div>
          ${data.revision_notes
            .map(
              (rn) => `
            <div class="revision-note-item">
              <span style="color: #059669; font-weight: bold;">✔</span>
              <span style="color: var(--text-secondary);">${escapeHtml(rn)}</span>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  wrapper.innerHTML = html;
}

// -----------------------------------------------------------------------------
// IMPORTANT QUESTIONS MODULE
// -----------------------------------------------------------------------------
let questionsLoaded = false;
async function loadQuestions(docId, forceRegen = false) {
  if (questionsLoaded && !forceRegen) return;

  const contentDiv = document.getElementById("questionsListWrapper");
  const loadingDiv = document.getElementById("questionsLoadingWrapper");
  const regenBtn = document.getElementById("regenQuestionsBtn");

  if (contentDiv) contentDiv.style.display = "none";
  if (loadingDiv) loadingDiv.style.display = "block";
  if (regenBtn) regenBtn.disabled = true;

  try {
    const res = await safeApiFetch(`/api/content/questions/${docId}${forceRegen ? "?regenerate=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    renderQuestionsUI(res.data);
    questionsLoaded = true;
  } catch (err) {
    if (contentDiv) {
      contentDiv.innerHTML = `
        <div class="retry-error-card">
          <h3>⚠️ Notice on AI Generation</h3>
          <p>${escapeHtml(err.message)}</p>
          <button class="btn btn-primary btn-sm" onclick="loadQuestions(${docId}, true)">🔄 Try Again</button>
        </div>
      `;
      contentDiv.style.display = "block";
    }
  } finally {
    if (loadingDiv) loadingDiv.style.display = "none";
    if (contentDiv) contentDiv.style.display = "block";
    if (regenBtn) regenBtn.disabled = false;
  }
}

function renderQuestionsUI(questions) {
  const wrapper = document.getElementById("questionsListWrapper");
  if (!wrapper) return;

  if (!questions || questions.length === 0) {
    wrapper.innerHTML = `<p class="form-hint">No questions generated.</p>`;
    return;
  }

  let html = "";
  questions.forEach((q, idx) => {
    const qNum = idx + 1;
    html += `
      <div class="question-card" id="q-card-${idx}">
        <div class="question-header" onclick="toggleQuestion(${idx})">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span class="badge badge-primary">Q${qNum}</span>
            <span style="font-weight: 700; color: var(--text-primary); font-size: 1rem;">${escapeHtml(q.question)}</span>
          </div>
          <svg class="question-toggle-arrow" id="q-arrow-${idx}" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>

        <div class="question-body" id="q-body-${idx}">
          <div style="margin-bottom: 0.75rem;">
            <strong style="color: var(--text-primary); display: block; margin-bottom: 0.25rem;">Answer:</strong>
            <div style="color: var(--text-secondary); line-height: 1.6;">${escapeHtml(q.answer)}</div>
          </div>
          ${
            q.explanation
              ? `
            <div class="tip-callout">
              <strong>Exam Tip:</strong> ${escapeHtml(q.explanation)}
            </div>
          `
              : ""
          }
        </div>
      </div>
    `;
  });

  wrapper.innerHTML = html;
}

window.toggleQuestion = function (idx) {
  const body = document.getElementById(`q-body-${idx}`);
  const arrow = document.getElementById(`q-arrow-${idx}`);
  if (!body) return;

  if (body.style.display === "none") {
    body.style.display = "block";
    if (arrow) arrow.style.transform = "rotate(180deg)";
  } else {
    body.style.display = "none";
    if (arrow) arrow.style.transform = "rotate(0deg)";
  }
};

// -----------------------------------------------------------------------------
// FLASHCARDS MODULE (3D INTERACTIVE FLIP & MASTERY TRACKING)
// -----------------------------------------------------------------------------
let flashcardsLoaded = false;
let currentFlashcards = [];
let currentCardIndex = 0;
let masteredCards = new Set();

async function loadFlashcards(docId, forceRegen = false) {
  if (flashcardsLoaded && !forceRegen) return;

  const contentDiv = document.getElementById("flashcardsStageWrapper");
  const loadingDiv = document.getElementById("flashcardsLoadingWrapper");
  const regenBtn = document.getElementById("regenFlashcardsBtn");

  if (contentDiv) contentDiv.style.display = "none";
  if (loadingDiv) loadingDiv.style.display = "block";
  if (regenBtn) regenBtn.disabled = true;

  try {
    const res = await safeApiFetch(`/api/content/flashcards/${docId}${forceRegen ? "?regenerate=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    currentFlashcards = res.data || [];
    currentCardIndex = 0;
    masteredCards.clear();
    initFlashcardsUI();
    updateMasteryUI();
    flashcardsLoaded = true;
  } catch (err) {
    if (contentDiv) {
      contentDiv.innerHTML = `
        <div class="retry-error-card">
          <h3>⚠️ Notice on AI Generation</h3>
          <p>${escapeHtml(err.message)}</p>
          <button class="btn btn-primary btn-sm" onclick="loadFlashcards(${docId}, true)">🔄 Try Again</button>
        </div>
      `;
      contentDiv.style.display = "block";
    }
  } finally {
    if (loadingDiv) loadingDiv.style.display = "none";
    if (contentDiv) contentDiv.style.display = "block";
    if (regenBtn) regenBtn.disabled = false;
  }
}

function updateMasteryUI() {
  const countText = document.getElementById("masteryCountText");
  const fill = document.getElementById("masteryProgressFill");
  if (!currentFlashcards.length) return;

  const total = currentFlashcards.length;
  const count = masteredCards.size;
  const pct = Math.round((count / total) * 100);

  if (countText) countText.textContent = `${count} of ${total} Mastered (${pct}%)`;
  if (fill) fill.style.width = `${pct}%`;
}

function initFlashcardsUI() {
  const cardInner = document.getElementById("flashcardInner");
  const prevBtn = document.getElementById("prevCardBtn");
  const nextBtn = document.getElementById("nextCardBtn");
  const flipBtn = document.getElementById("flipCardBtn");
  const markMasteredBtn = document.getElementById("markMasteredBtn");
  const markNeedsReviewBtn = document.getElementById("markNeedsReviewBtn");
  const resetMasteryBtn = document.getElementById("resetMasteryBtn");

  if (!cardInner) return;

  cardInner.onclick = (e) => {
    // Avoid re-flipping if clicking action buttons inside the card
    if (e.target.closest(".flashcard-mastery-actions")) return;
    cardInner.classList.toggle("flipped");
  };

  if (flipBtn) {
    flipBtn.onclick = () => {
      cardInner.classList.toggle("flipped");
    };
  }

  if (markMasteredBtn) {
    markMasteredBtn.onclick = (e) => {
      e.stopPropagation();
      masteredCards.add(currentCardIndex);
      updateMasteryUI();
      if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        showFlashcard(currentCardIndex);
      }
    };
  }

  if (markNeedsReviewBtn) {
    markNeedsReviewBtn.onclick = (e) => {
      e.stopPropagation();
      masteredCards.delete(currentCardIndex);
      updateMasteryUI();
      if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        showFlashcard(currentCardIndex);
      }
    };
  }

  if (resetMasteryBtn) {
    resetMasteryBtn.onclick = () => {
      masteredCards.clear();
      updateMasteryUI();
    };
  }

  if (prevBtn) {
    prevBtn.onclick = () => {
      if (currentCardIndex > 0) {
        currentCardIndex--;
        showFlashcard(currentCardIndex);
      }
    };
  }

  if (nextBtn) {
    nextBtn.onclick = () => {
      if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        showFlashcard(currentCardIndex);
      }
    };
  }

  document.addEventListener("keydown", (e) => {
    const pane = document.getElementById("flashcardsPane");
    if (!pane || !pane.classList.contains("active")) return;

    if (e.key === "ArrowLeft" && currentCardIndex > 0) {
      currentCardIndex--;
      showFlashcard(currentCardIndex);
    } else if (e.key === "ArrowRight" && currentCardIndex < currentFlashcards.length - 1) {
      currentCardIndex++;
      showFlashcard(currentCardIndex);
    } else if (e.key === " " || e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      cardInner.classList.toggle("flipped");
    } else if (e.key === "1") {
      masteredCards.delete(currentCardIndex);
      updateMasteryUI();
      if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        showFlashcard(currentCardIndex);
      }
    } else if (e.key === "2") {
      masteredCards.add(currentCardIndex);
      updateMasteryUI();
      if (currentCardIndex < currentFlashcards.length - 1) {
        currentCardIndex++;
        showFlashcard(currentCardIndex);
      }
    }
  });

  showFlashcard(0);
}

function showFlashcard(index) {
  const cardInner = document.getElementById("flashcardInner");
  const frontText = document.getElementById("cardFrontText");
  const backText = document.getElementById("cardBackText");
  const hintText = document.getElementById("cardFrontHint");
  const counter = document.getElementById("flashcardCounter");
  const prevBtn = document.getElementById("prevCardBtn");
  const nextBtn = document.getElementById("nextCardBtn");

  if (!currentFlashcards || currentFlashcards.length === 0) return;

  if (cardInner) cardInner.classList.remove("flipped");

  const card = currentFlashcards[index];
  if (frontText) frontText.textContent = card.front || "";
  if (backText) backText.textContent = card.back || "";
  if (hintText) hintText.textContent = card.hint ? `Category: ${card.hint}` : "";
  if (counter) counter.textContent = `Card ${index + 1} of ${currentFlashcards.length}`;

  if (prevBtn) prevBtn.disabled = index === 0;
  if (nextBtn) nextBtn.disabled = index === currentFlashcards.length - 1;
}

// -----------------------------------------------------------------------------
// MCQ QUIZ MODULE
// -----------------------------------------------------------------------------
let quizLoaded = false;
let currentMCQs = [];
let quizUserAnswers = {};

async function loadQuiz(docId, forceRegen = false) {
  if (quizLoaded && !forceRegen) return;

  const contentDiv = document.getElementById("quizContentWrapper");
  const loadingDiv = document.getElementById("quizLoadingWrapper");
  const regenBtn = document.getElementById("regenQuizBtn");

  if (contentDiv) contentDiv.style.display = "none";
  if (loadingDiv) loadingDiv.style.display = "block";
  if (regenBtn) regenBtn.disabled = true;

  try {
    const res = await safeApiFetch(`/api/content/mcqs/${docId}${forceRegen ? "?regenerate=true" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    currentMCQs = res.data || [];
    quizUserAnswers = {};
    renderQuizUI(docId);
    quizLoaded = true;
  } catch (err) {
    if (contentDiv) {
      contentDiv.innerHTML = `
        <div class="retry-error-card">
          <h3>⚠️ Notice on AI Generation</h3>
          <p>${escapeHtml(err.message)}</p>
          <button class="btn btn-primary btn-sm" onclick="loadQuiz(${docId}, true)">🔄 Try Again</button>
        </div>
      `;
      contentDiv.style.display = "block";
    }
  } finally {
    if (loadingDiv) loadingDiv.style.display = "none";
    if (contentDiv) contentDiv.style.display = "block";
    if (regenBtn) regenBtn.disabled = false;
  }
}

function renderQuizUI(docId) {
  const wrapper = document.getElementById("quizContentWrapper");
  if (!wrapper) return;

  if (!currentMCQs || currentMCQs.length === 0) {
    wrapper.innerHTML = `<p class="form-hint">No questions available.</p>`;
    return;
  }

  let html = `<div class="quiz-container">`;

  currentMCQs.forEach((mcq, qIdx) => {
    const qNum = qIdx + 1;
    html += `
      <div class="quiz-card" id="quiz-card-${qIdx}">
        <div class="quiz-question-number">Question ${qNum} of ${currentMCQs.length}</div>
        <div class="quiz-question-text">${escapeHtml(mcq.question)}</div>
        <div class="quiz-options-list">
          ${mcq.options
            .map((opt, optIdx) => {
              const letter = ["A", "B", "C", "D"][optIdx];
              return `
              <button class="quiz-option-btn" id="q${qIdx}-opt-${letter}" onclick="selectQuizOption(${qIdx}, '${letter}', '${escapeHtml(mcq.correct_answer)}', ${docId})">
                <span class="option-badge">${letter}</span>
                <span>${escapeHtml(opt)}</span>
              </button>
            `;
            })
            .join("")}
        </div>
        <div class="quiz-explanation-box" id="q${qIdx}-exp">
          <strong>Explanation:</strong> ${escapeHtml(mcq.explanation || "Correct answer based on the study material.")}
        </div>
      </div>
    `;
  });

  html += `
    <div id="quizResultBox" style="display: none;" class="quiz-result-card">
      <div style="font-size: 2.25rem;">🏆</div>
      <h2 style="font-size: 1.5rem; font-weight: 800; margin-top: 0.5rem;">Quiz Completed!</h2>
      <div class="quiz-result-score" id="quizFinalScoreDisplay">0 / 5</div>
      <p id="quizScoreFeedback" style="color: var(--text-muted); margin-bottom: 1.5rem;">Great work testing your knowledge.</p>
      <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
        <button class="btn btn-primary" onclick="restartQuiz(${docId})">Retake Quiz</button>
        <button class="btn btn-secondary" onclick="reviewQuiz()">Review Answers</button>
        <a href="/export/mcqs/${docId}" class="btn btn-outline">Download Quiz PDF</a>
      </div>
    </div>
  </div>`;

  wrapper.innerHTML = html;
}

window.selectQuizOption = function (qIdx, selectedLetter, correctLetter, docId) {
  if (quizUserAnswers[qIdx] !== undefined) return;

  quizUserAnswers[qIdx] = selectedLetter;

  const card = document.getElementById(`quiz-card-${qIdx}`);
  const buttons = card.querySelectorAll(".quiz-option-btn");
  const expBox = document.getElementById(`q${qIdx}-exp`);

  const normCorrect = correctLetter.trim().toUpperCase();
  const isCorrect = selectedLetter === normCorrect;

  buttons.forEach((btn) => {
    btn.disabled = true;
    const btnLetter = btn.id.split("-opt-")[1];
    if (btnLetter === normCorrect) {
      btn.classList.add("correct");
    } else if (btnLetter === selectedLetter && !isCorrect) {
      btn.classList.add("incorrect");
    }
  });

  if (expBox) expBox.style.display = "block";

  if (Object.keys(quizUserAnswers).length === currentMCQs.length) {
    calculateAndSubmitQuiz(docId);
  }
};

async function calculateAndSubmitQuiz(docId) {
  let score = 0;
  currentMCQs.forEach((mcq, idx) => {
    const normCorrect = mcq.correct_answer.trim().toUpperCase();
    if (quizUserAnswers[idx] === normCorrect) {
      score++;
    }
  });

  const resultBox = document.getElementById("quizResultBox");
  const scoreDisplay = document.getElementById("quizFinalScoreDisplay");
  const feedback = document.getElementById("quizScoreFeedback");

  if (scoreDisplay) scoreDisplay.textContent = `${score} / ${currentMCQs.length}`;
  if (feedback) {
    const pct = (score / currentMCQs.length) * 100;
    if (pct === 100) feedback.innerHTML = `<span style="color: #059669; font-weight: 700;">🎉 Perfect Score! Outstanding Mastery!</span> You know this material inside out.`;
    else if (pct >= 80) feedback.innerHTML = `<span style="color: #059669; font-weight: 700;">🌟 Excellent job!</span> Strong comprehension of this document.`;
    else if (pct >= 60) feedback.textContent = "Good attempt! Review the flashcards and questions to strengthen weak spots.";
    else feedback.textContent = "Keep practicing! Use the AI Summary and Flashcards to brush up.";
  }

  if (resultBox) {
    resultBox.style.display = "block";
    resultBox.scrollIntoView({ behavior: "smooth" });
  }

  try {
    await safeApiFetch(`/api/quiz/submit/${docId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        score: score,
        total_questions: currentMCQs.length,
        details: quizUserAnswers,
      }),
    });
  } catch (err) {
    console.warn("Quiz result could not be saved to history:", err);
  }
}

window.restartQuiz = function (docId) {
  quizUserAnswers = {};
  renderQuizUI(docId);
};

window.reviewQuiz = function () {
  const firstCard = document.getElementById("quiz-card-0");
  if (firstCard) firstCard.scrollIntoView({ behavior: "smooth" });
};

// -----------------------------------------------------------------------------
// AI STUDY ASSISTANT / CHAT MODULE
// -----------------------------------------------------------------------------
let chatInitialized = false;
let currentChatMode = "normal";

async function initChat(docId) {
  if (chatInitialized) return;

  const chatContainer = document.getElementById("chatMessages");
  const chatInput = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSendBtn");
  const clearBtn = document.getElementById("clearChatBtn");

  // Mode pills
  document.querySelectorAll(".chat-mode-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".chat-mode-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      currentChatMode = pill.dataset.mode;
      if (chatInput) {
        chatInput.focus();
        const placeholders = {
          normal: "Ask any question about this document...",
          explain_simply: "What topic should I explain in simple words?",
          summarize: "What part of the document would you like summarized?",
          give_example: "What concept would you like a practical example for?",
          ask_questions: "Ask me 5 questions to test my understanding of...",
          exam_answer: "What exam question should I write a model answer for?",
        };
        chatInput.placeholder = placeholders[currentChatMode] || placeholders.normal;
      }
    });
  });

  // Quick Suggestion Chips
  document.querySelectorAll(".chat-chip-btn").forEach((chip) => {
    chip.onclick = () => {
      const prompt = chip.dataset.prompt;
      const mode = chip.dataset.mode;
      if (chatInput && prompt) {
        chatInput.value = prompt;
        if (mode) {
          const matchingPill = document.querySelector(`.chat-mode-pill[data-mode="${mode}"]`);
          if (matchingPill) matchingPill.click();
        }
        handleSendMessage();
      }
    };
  });

  // Load chat history safely
  try {
    const res = await safeApiFetch(`/api/chat/${docId}`);
    if (res.success && res.history && res.history.length > 0) {
      chatContainer.innerHTML = "";
      res.history.forEach((msg) => {
        appendMessageUI(msg.role, msg.message);
      });
    }
    scrollChatToBottom();
  } catch (err) {
    console.warn("Could not load previous chat history:", err);
  }

  // Send message handler
  async function handleSendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessageUI("user", text);
    chatInput.value = "";
    scrollChatToBottom();

    const typingId = appendTypingIndicator();
    scrollChatToBottom();

    if (sendBtn) sendBtn.disabled = true;

    try {
      const res = await safeApiFetch(`/api/chat/${docId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, mode: currentChatMode }),
      });

      removeTypingIndicator(typingId);
      appendMessageUI("assistant", res.answer);
    } catch (err) {
      removeTypingIndicator(typingId);
      appendMessageUI("assistant", `⚠️ ${err.message}`);
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      scrollChatToBottom();
    }
  }

  if (sendBtn) sendBtn.onclick = handleSendMessage;
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });
  }

  // Clear chat
  if (clearBtn) {
    clearBtn.onclick = async () => {
      if (confirm("Are you sure you want to clear your chat history for this document?")) {
        try {
          await safeApiFetch(`/api/chat/clear/${docId}`, { method: "POST" });
          chatContainer.innerHTML = `
            <div class="chat-msg chat-msg-assistant">
              <div class="msg-avatar msg-avatar-ai">🤖</div>
              <div class="msg-bubble">
                Chat history cleared. I'm ready to answer any questions about your study material!
              </div>
            </div>
          `;
        } catch (err) {
          alert(`Failed to clear chat: ${err.message}`);
        }
      }
    };
  }

  chatInitialized = true;
}

function appendMessageUI(role, text) {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-msg chat-msg-${role}`;

  const avatar = document.createElement("div");
  avatar.className = `msg-avatar msg-avatar-${role === "user" ? "user" : "ai"}`;
  avatar.textContent = role === "user" ? "👤" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";

  if (role === "assistant") {
    bubble.innerHTML = formatMarkdownToHTML(text);
  } else {
    bubble.textContent = text;
  }

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  container.appendChild(msgDiv);
}

function appendTypingIndicator() {
  const container = document.getElementById("chatMessages");
  if (!container) return null;

  const id = "typing-" + Date.now();
  const div = document.createElement("div");
  div.id = id;
  div.className = "chat-msg chat-msg-assistant";
  div.innerHTML = `
    <div class="msg-avatar msg-avatar-ai">🤖</div>
    <div class="msg-bubble" style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-muted);">
      <span class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></span>
      <span>Thinking & searching document context...</span>
    </div>
  `;
  container.appendChild(div);
  return id;
}

function removeTypingIndicator(id) {
  if (!id) return;
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollChatToBottom() {
  const container = document.getElementById("chatMessages");
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// -----------------------------------------------------------------------------
// Utilities
// -----------------------------------------------------------------------------
function escapeHtml(string) {
  if (!string) return "";
  return String(string)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatMarkdownToHTML(md) {
  if (!md) return "";
  let html = escapeHtml(md);

  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, "<code style='background: #E2E8F0; padding: 2px 4px; border-radius: 4px; font-size: 0.85em;'>$1</code>");
  // Bullet lists
  html = html.replace(/^\s*[•\-]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/s, "<ul style='padding-left: 1.25rem; margin: 0.5rem 0;'>$1</ul>");
  // Paragraphs
  html = html.replace(/\n\n+/g, "</p><p style='margin-top: 0.5rem;'>");
  html = html.replace(/\n/g, "<br/>");

  return `<p>${html}</p>`;
}
