/**
 * AutoJobHunt Extension — Content Script (v1.1.0)
 * Runs directly in your active logged-in browser session across all job portals.
 * Fully self-contained — immune to page Content Security Policy (CSP).
 */

(function () {
  // Prevent duplicate injection
  if (window.__AUTOJOBHUNT_INJECTED__) return;
  window.__AUTOJOBHUNT_INJECTED__ = true;

  // Base profile config (overridden dynamically by local dashboard)
  let cand = {
    full_name: "Rishi Thakur",
    first_name: "Rishi",
    last_name: "Thakur",
    email: "rishi_th219@proton.me",
    phone: "8109830219",
    phone_with_code: "+918109830219",
    location: "Bengaluru, India",
    city: "Bengaluru",
    state: "Karnataka",
    country: "India",
    linkedin: "https://linkedin.com/in/rishi-thakur-b665a4298",
    github: "https://github.com/rishi-th219",
    current_org: "Open to Opportunities",
    notice_period: "Immediate / 15 Days",
    years_experience: "1",
    education: "M.Tech in CSE (Specialization: Data Science & Artificial Intelligence — DSAI), IIIT Naya Raipur",
    degree: "Master's Degree",
    school: "IIIT Naya Raipur",
    discipline: "Computer Science and Engineering",
    authorized_in_country: "Yes",
    require_sponsorship: "No"
  };

  // Asynchronously refresh candidate details from localhost dashboard
  fetch("http://127.0.0.1:5000/api/profile")
    .then(r => r.json())
    .then(data => {
      if (data && data.full_name) {
        cand = Object.assign(cand, data);
      }
    })
    .catch(() => {
      // Local server offline or busy; embedded candidate config is used
    });

  // Native Value Setter for React, Angular, Vue
  function setFieldValue(el, val) {
    if (!el || val === undefined || val === null) return false;
    try {
      el.focus();
      const valueSetter = Object.getOwnPropertyDescriptor(el, 'value')?.set;
      const prototype = Object.getPrototypeOf(el);
      const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
      if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {
        prototypeValueSetter.call(el, val);
      } else if (valueSetter) {
        valueSetter.call(el, val);
      } else {
        el.value = val;
      }
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      el.dispatchEvent(new Event('blur', { bubbles: true }));

      el.style.outline = "2px solid #10b981";
      el.style.backgroundColor = "rgba(16, 185, 129, 0.06)";
      return true;
    } catch (err) {
      console.warn("[AutoJobHunt] Error setting value:", err);
      return false;
    }
  }

  function getFieldDescriptor(el) {
    let desc = [
      el.name || "",
      el.id || "",
      el.placeholder || "",
      el.getAttribute("aria-label") || "",
      el.getAttribute("data-test") || "",
      el.getAttribute("data-automation-id") || "",
      el.getAttribute("autocomplete") || ""
    ];
    if (el.labels && el.labels[0]) desc.push(el.labels[0].innerText || "");
    const parent = el.closest(".field, .form-group, .question, label, div[class*='field'], div[class*='form'], div[class*='input']");
    if (parent) {
      desc.push(parent.innerText ? parent.innerText.slice(0, 160) : "");
    }
    return desc.join(" ").toLowerCase();
  }

  // Master Autofill Routine
  function executeAutofill() {
    let count = 0;

    // Reveal hidden form if button exists
    const applyBtns = document.querySelectorAll("a[href*='#apply'], button:has-text('Apply'), a:has-text('Apply'), button:has-text('Apply Now'), a:has-text('Apply for this job')");
    for (const b of applyBtns) {
      if (b.offsetParent !== null) {
        try { b.click(); } catch(e) {}
        break;
      }
    }

    const inputs = document.querySelectorAll("input, textarea, select");
    inputs.forEach(el => {
      const type = (el.type || "").toLowerCase();
      if (type === "hidden" || type === "submit" || type === "button" || type === "file") return;

      const desc = getFieldDescriptor(el);

      // Skip already populated fields unless it's notice period / experience
      if (el.value && el.value.trim().length > 0 && !desc.includes("notice") && !desc.includes("experience") && !desc.includes("period")) {
        return;
      }

      // First Name
      if (/\b(first\s*name|given\s*name|fname)\b/.test(desc)) {
        if (setFieldValue(el, cand.first_name)) count++;
      }
      // Last Name
      else if (/\b(last\s*name|family\s*name|surname|lname)\b/.test(desc)) {
        if (setFieldValue(el, cand.last_name)) count++;
      }
      // Full Name
      else if (/\b(full\s*name|candidate\s*name|your\s*name|legal\s*name)\b/.test(desc) || (desc.includes("name") && !desc.includes("first") && !desc.includes("last") && !desc.includes("company") && !desc.includes("school") && !desc.includes("user"))) {
        if (setFieldValue(el, cand.full_name)) count++;
      }
      // Email
      else if (/\b(email|e-mail|electronic\s*mail)\b/.test(desc) || type === "email") {
        if (setFieldValue(el, cand.email)) count++;
      }
      // Phone / Mobile
      else if (/\b(phone|mobile|cell|contact\s*number|telephone)\b/.test(desc) || type === "tel") {
        const phoneVal = desc.includes("country code") || desc.includes("+") ? cand.phone_with_code : cand.phone;
        if (setFieldValue(el, phoneVal)) count++;
      }
      // LinkedIn
      else if (/\b(linkedin|linked\s*in)\b/.test(desc)) {
        if (setFieldValue(el, cand.linkedin)) count++;
      }
      // GitHub
      else if (/\b(github|git\s*hub)\b/.test(desc)) {
        if (setFieldValue(el, cand.github)) count++;
      }
      // Portfolio / Website
      else if (/\b(portfolio|website|personal\s*website|blog)\b/.test(desc)) {
        if (setFieldValue(el, cand.github || cand.linkedin)) count++;
      }
      // Current Organization / Company
      else if (/\b(current\s*company|current\s*org|employer|current\s*employer|company\s*name)\b/.test(desc)) {
        if (setFieldValue(el, cand.current_org)) count++;
      }
      // City / Location
      else if (/\b(city|current\s*location|location|residence)\b/.test(desc) && !desc.includes("address")) {
        if (setFieldValue(el, cand.city)) count++;
      }
      // Notice Period
      else if (/\b(notice\s*period|notice|availability|how\s*soon|joining\s*time)\b/.test(desc)) {
        if (setFieldValue(el, cand.notice_period)) count++;
      }
      // Years of Experience
      else if (/\b(years\s*of\s*experience|total\s*experience|experience\s*in\s*years|yoe)\b/.test(desc)) {
        if (setFieldValue(el, cand.years_experience)) count++;
      }
      // Education / Degree / College
      else if (/\b(school|university|college|institution)\b/.test(desc)) {
        if (setFieldValue(el, cand.school)) count++;
      }
      else if (/\b(degree|highest\s*degree|qualification)\b/.test(desc)) {
        if (setFieldValue(el, cand.degree)) count++;
      }
      else if (/\b(discipline|major|field\s*of\s*study|stream)\b/.test(desc)) {
        if (setFieldValue(el, cand.discipline)) count++;
      }
      // Salary / CTC
      else if (/\b(expected\s*ctc|expected\s*salary|desired\s*salary|compensation|salary\s*expectation)\b/.test(desc)) {
        if (setFieldValue(el, "Market Standard / Negotiable")) count++;
      }
      // Textarea cover letter / "Why this role?"
      else if (el.tagName === "TEXTAREA" && (desc.includes("cover") || desc.includes("why") || desc.includes("note") || desc.includes("summary") || desc.includes("additional"))) {
        const note = `I am very excited to apply for this opportunity. With an M.Tech in Computer Science & AI (specializing in Machine Learning, predictive modeling, and scalable data solutions) and hands-on experience building production workflows, I bring strong problem-solving capabilities, rapid execution, and technical discipline to this team. I look forward to contributing immediately.`;
        if (setFieldValue(el, note)) count++;
      }
      // Radio buttons
      else if (type === "radio") {
        if (desc.includes("authorized") || desc.includes("eligible") || desc.includes("legally")) {
          if (el.value.toLowerCase().includes("yes") || desc.includes("yes")) {
            el.checked = true;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            count++;
          }
        } else if (desc.includes("sponsor") || desc.includes("visa")) {
          if (el.value.toLowerCase().includes("no") || desc.includes("no")) {
            el.checked = true;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            count++;
          }
        }
      }
    });

    // Dropdowns (Select Elements)
    document.querySelectorAll("select").forEach(sel => {
      const desc = getFieldDescriptor(sel);
      let targetText = "";

      if (desc.includes("authorized") || desc.includes("legally")) targetText = "yes";
      else if (desc.includes("sponsor") || desc.includes("visa")) targetText = "no";
      else if (desc.includes("gender")) targetText = "prefer not to say|decline";
      else if (desc.includes("veteran")) targetText = "not a veteran|decline|prefer not";
      else if (desc.includes("disability")) targetText = "do not have|decline|prefer not";

      if (targetText) {
        const patterns = targetText.split("|");
        for (let opt of sel.options) {
          const oText = (opt.text || "").toLowerCase();
          if (patterns.some(p => oText.includes(p))) {
            sel.value = opt.value;
            sel.dispatchEvent(new Event("change", { bubbles: true }));
            sel.style.outline = "2px solid #10b981";
            count++;
            break;
          }
        }
      }
    });

    return count;
  }

  // Floating Action Pill on Job Pages
  function injectFloatingWidget() {
    if (document.getElementById("ajh-extension-widget")) return;

    const widget = document.createElement("div");
    widget.id = "ajh-extension-widget";
    widget.innerHTML = `
      <div id="ajh-widget-pill" style="
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 2147483647;
        background: #0f172a;
        color: #f8fafc;
        border: 1px solid #10b981;
        border-radius: 30px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        padding: 6px 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: system-ui, -apple-system, sans-serif;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
      ">
        <span style="color:#10b981; font-size:16px;">⚡</span>
        <span id="ajh-btn-label">AutoFill Application</span>
        <button id="ajh-btn-dismiss" style="
          background: transparent;
          border: none;
          color: #94a3b8;
          font-size: 14px;
          cursor: pointer;
          margin-left: 4px;
          padding: 0;
        " title="Hide widget">✕</button>
      </div>
    `;

    document.documentElement.appendChild(widget);

    const pill = widget.querySelector("#ajh-widget-pill");
    const label = widget.querySelector("#ajh-btn-label");
    const dismiss = widget.querySelector("#ajh-btn-dismiss");

    dismiss.addEventListener("click", (e) => {
      e.stopPropagation();
      widget.remove();
    });

    pill.addEventListener("click", () => {
      label.innerText = "Filling...";
      const filled = executeAutofill();
      label.innerText = `✓ ${filled} Fields Filled!`;
      pill.style.background = "#064e3b";
      pill.style.borderColor = "#34d399";

      // Offer Mark Applied option
      setTimeout(() => {
        if (!document.getElementById("ajh-applied-btn")) {
          const appliedBtn = document.createElement("button");
          appliedBtn.id = "ajh-applied-btn";
          appliedBtn.innerText = "✓ Mark Applied in Dashboard";
          appliedBtn.style.cssText = `
            background: #10b981;
            color: #0f172a;
            font-weight: 700;
            border: none;
            border-radius: 20px;
            padding: 4px 10px;
            font-size: 11px;
            cursor: pointer;
            margin-left: 6px;
          `;
          appliedBtn.onclick = async (ev) => {
            ev.stopPropagation();
            appliedBtn.innerText = "Saving...";
            try {
              await fetch("http://127.0.0.1:5000/api/mark-applied", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  url: window.location.href,
                  company: document.title.split("-")[0].trim() || "Applied Company",
                  role: document.title.split("-")[1]?.trim() || "Role"
                })
              });
              appliedBtn.innerText = "✓ Tracked!";
              appliedBtn.style.background = "#059669";
              appliedBtn.style.color = "#ffffff";
            } catch (err) {
              appliedBtn.innerText = "✓ Saved!";
            }
          };
          pill.appendChild(appliedBtn);
        }
      }, 500);
    });
  }

  // Detect job application pages or forms
  function evaluatePage() {
    const isJobSite = /greenhouse\.io|lever\.co|ashbyhq\.com|smartrecruiters\.com|myworkdayjobs\.com|workday\.com|naukri\.com|instahyre\.com|linkedin\.com\/jobs|indeed\.com/i.test(window.location.href);
    const hasFormInputs = document.querySelectorAll("input[type='email'], input[name*='name'], input[id*='name'], textarea, input[name*='phone']").length >= 2;

    if (isJobSite || hasFormInputs) {
      injectFloatingWidget();
    }
  }

  // Listen for execution commands from extension popup
  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
      if (req.action === "autofill_now") {
        const count = executeAutofill();
        sendResponse({ status: "ok", filled: count });
      }
    });
  }

  // Run on load and observe dynamically loaded modals (React SPAs)
  setTimeout(evaluatePage, 800);
  setTimeout(evaluatePage, 2500);
  const obs = new MutationObserver(() => evaluatePage());
  obs.observe(document.body || document.documentElement, { childList: true, subtree: true });

})();
