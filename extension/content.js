// AutoJobHunt Extension Content Script
// Automatically detects job application forms and enables 1-click in-browser autofill in your logged-in session.

function injectAutofillButton() {
  if (document.getElementById("ajh-extension-trigger-btn")) return;

  const btn = document.createElement("button");
  btn.id = "ajh-extension-trigger-btn";
  btn.innerHTML = "⚡ AutoFill Application (AutoJobHunt)";
  btn.style.position = "fixed";
  btn.style.top = "18px";
  btn.style.right = "18px";
  btn.style.zIndex = "9999999";
  btn.style.backgroundColor = "#10b981";
  btn.style.color = "#0f172a";
  btn.style.fontWeight = "bold";
  btn.style.fontSize = "12px";
  btn.style.padding = "8px 14px";
  btn.style.border = "none";
  btn.style.borderRadius = "8px";
  btn.style.boxShadow = "0 4px 15px rgba(0,0,0,0.3)";
  btn.style.cursor = "pointer";
  btn.style.fontFamily = "system-ui, sans-serif";
  btn.style.transition = "transform 0.15s ease, background 0.15s";

  btn.onmouseover = () => btn.style.transform = "scale(1.04)";
  btn.onmouseout = () => btn.style.transform = "scale(1.0)";

  btn.onclick = () => {
    btn.innerHTML = "⏳ Filling...";
    // Inject autofill logic
    const s = document.createElement("script");
    s.src = "http://127.0.0.1:5000/autofill.js?t=" + Date.now();
    document.body.appendChild(s);
    setTimeout(() => {
      btn.innerHTML = "✓ Autofilled!";
      btn.style.backgroundColor = "#059669";
      btn.style.color = "#ffffff";
    }, 800);
  };

  document.body.appendChild(btn);
}

// Check if page has application form inputs
function checkForApplicationForm() {
  const inputs = document.querySelectorAll("input[type='text'], input[type='email'], input[name*='name'], input[id*='name'], textarea");
  if (inputs.length >= 2) {
    injectAutofillButton();
  }
}

// Run on load and after DOM mutations (for SPAs)
setTimeout(checkForApplicationForm, 1000);
setTimeout(checkForApplicationForm, 2500);
const observer = new MutationObserver(() => checkForApplicationForm());
observer.observe(document.body, { childList: true, subtree: true });
