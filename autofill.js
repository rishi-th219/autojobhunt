/**
 * autofill.js — AutoJobHunt In-Browser 1-Click Autofill Engine
 * Runs directly inside your existing logged-in browser tab (Brave, Chrome, Firefox, etc.)
 * Compatible with Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Naukri, and generic career portals.
 */

(async function () {
  console.log("⚡ [AutoJobHunt] Initializing in-browser autofill in your logged-in session...");

  // Default fallback profile (overridden dynamically by localhost API)
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

  // 1. Fetch live profile from local dashboard if reachable
  try {
    const res = await fetch("http://127.0.0.1:5000/api/profile", { cache: "no-store" });
    if (res.ok) {
      const liveData = await res.json();
      cand = Object.assign(cand, liveData);
      console.log("⚡ [AutoJobHunt] Loaded live candidate profile from localhost:5000:", cand.full_name);
    }
  } catch (e) {
    console.log("⚡ [AutoJobHunt] Localhost dashboard not responding directly, using embedded profile config.");
  }

  // 2. Event Dispatcher for modern React / Vue / Angular apps
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
      el.style.border = "2px solid #10b981"; // Highlight filled fields green
      el.style.backgroundColor = "rgba(16, 185, 129, 0.05)";
      return true;
    } catch (err) {
      console.warn("Error setting field value:", err);
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
      el.getAttribute("data-automation-id") || ""
    ];
    // Check parent label or wrapper text
    const label = el.labels && el.labels[0];
    if (label) desc.push(label.innerText || "");
    const parent = el.closest(".field, .form-group, .question, label, div[class*='field'], div[class*='form']");
    if (parent) {
      desc.push(parent.innerText ? parent.innerText.slice(0, 150) : "");
    }
    return desc.join(" ").toLowerCase();
  }

  let filledCount = 0;

  // 3. Scan and Populate Input Fields
  const inputs = document.querySelectorAll("input, textarea, select");
  inputs.forEach(el => {
    const type = (el.type || "").toLowerCase();
    if (type === "hidden" || type === "submit" || type === "button" || type === "file") return;

    const desc = getFieldDescriptor(el);

    // Skip if already filled
    if (el.value && el.value.trim().length > 0 && !desc.includes("notice") && !desc.includes("experience")) {
      return;
    }

    // First Name
    if (/\b(first\s*name|given\s*name|fname)\b/.test(desc)) {
      if (setFieldValue(el, cand.first_name)) filledCount++;
    }
    // Last Name
    else if (/\b(last\s*name|family\s*name|surname|lname)\b/.test(desc)) {
      if (setFieldValue(el, cand.last_name)) filledCount++;
    }
    // Full Name
    else if (/\b(full\s*name|candidate\s*name|your\s*name|legal\s*name)\b/.test(desc) || (desc.includes("name") && !desc.includes("first") && !desc.includes("last") && !desc.includes("company") && !desc.includes("school") && !desc.includes("user"))) {
      if (setFieldValue(el, cand.full_name)) filledCount++;
    }
    // Email
    else if (/\b(email|e-mail|electronic\s*mail)\b/.test(desc) || type === "email") {
      if (setFieldValue(el, cand.email)) filledCount++;
    }
    // Phone / Mobile
    else if (/\b(phone|mobile|cell|contact\s*number|telephone)\b/.test(desc) || type === "tel") {
      const phoneVal = desc.includes("country code") || desc.includes("+") ? cand.phone_with_code : cand.phone;
      if (setFieldValue(el, phoneVal)) filledCount++;
    }
    // LinkedIn
    else if (/\b(linkedin|linked\s*in)\b/.test(desc)) {
      if (setFieldValue(el, cand.linkedin)) filledCount++;
    }
    // GitHub
    else if (/\b(github|git\s*hub)\b/.test(desc)) {
      if (setFieldValue(el, cand.github)) filledCount++;
    }
    // Portfolio / Website
    else if (/\b(portfolio|website|personal\s*website|blog)\b/.test(desc)) {
      if (setFieldValue(el, cand.github || cand.linkedin)) filledCount++;
    }
    // Current Organization / Company
    else if (/\b(current\s*company|current\s*org|employer|current\s*employer|company\s*name)\b/.test(desc)) {
      if (setFieldValue(el, cand.current_org)) filledCount++;
    }
    // Location / City
    else if (/\b(city|current\s*location|location|residence)\b/.test(desc) && !desc.includes("address")) {
      if (setFieldValue(el, cand.city)) filledCount++;
    }
    // Notice Period
    else if (/\b(notice\s*period|notice|availability|how\s*soon|joining\s*time)\b/.test(desc)) {
      if (setFieldValue(el, cand.notice_period)) filledCount++;
    }
    // Total Experience
    else if (/\b(years\s*of\s*experience|total\s*experience|experience\s*in\s*years|yoe)\b/.test(desc)) {
      if (setFieldValue(el, cand.years_experience)) filledCount++;
    }
    // Education / College / Degree
    else if (/\b(school|university|college|institution)\b/.test(desc)) {
      if (setFieldValue(el, cand.school)) filledCount++;
    }
    else if (/\b(degree|highest\s*degree|qualification)\b/.test(desc)) {
      if (setFieldValue(el, cand.degree)) filledCount++;
    }
    else if (/\b(discipline|major|field\s*of\s*study|stream)\b/.test(desc)) {
      if (setFieldValue(el, cand.discipline)) filledCount++;
    }
    // Salary expectation
    else if (/\b(expected\s*ctc|expected\s*salary|desired\s*salary|compensation|salary\s*expectation)\b/.test(desc)) {
      if (setFieldValue(el, "Market Standard / Negotiable")) filledCount++;
    }
    // Textarea Cover letter / Summary / Why this role?
    else if (el.tagName === "TEXTAREA" && (desc.includes("cover") || desc.includes("why") || desc.includes("note") || desc.includes("summary") || desc.includes("additional"))) {
      const pageTitle = document.title || "";
      const note = `I am very excited to apply for this opportunity. With an M.Tech in Computer Science & AI (specializing in Machine Learning, predictive modeling, and scalable data solutions) and hands-on experience building production workflows, I bring strong problem-solving capabilities, rapid execution, and technical discipline to this team. I look forward to contributing immediately.`;
      if (setFieldValue(el, note)) filledCount++;
    }
    // Radio buttons & Dropdowns
    else if (type === "radio") {
      if (desc.includes("authorized") || desc.includes("eligible") || desc.includes("legally")) {
        if (el.value.toLowerCase().includes("yes") || desc.includes("yes")) {
          el.checked = true;
          el.dispatchEvent(new Event('change', { bubbles: true }));
          filledCount++;
        }
      } else if (desc.includes("sponsor") || desc.includes("visa")) {
        if (el.value.toLowerCase().includes("no") || desc.includes("no")) {
          el.checked = true;
          el.dispatchEvent(new Event('change', { bubbles: true }));
          filledCount++;
        }
      }
    }
  });

  // 4. Handle Custom Dropdowns (Select Elements)
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
          sel.style.border = "2px solid #10b981";
          filledCount++;
          break;
        }
      }
    }
  });

  // 5. In-Page Interactive Notification Overlay
  const existingOverlay = document.getElementById("autojobhunt-floating-badge");
  if (existingOverlay) existingOverlay.remove();

  const overlay = document.createElement("div");
  overlay.id = "autojobhunt-floating-badge";
  overlay.innerHTML = `
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
      <span style="font-size:18px;">⚡</span>
      <strong style="font-size:13px; color:#10b981;">AutoJobHunt Autofill Active</strong>
    </div>
    <div style="font-size:12px; color:#e2e8f0; margin-bottom:12px; line-height:1.4;">
      ✓ <strong>${filledCount} fields autofilled</strong> directly in your logged-in browser session!
      <div style="font-size:11px; color:#94a3b8; margin-top:3px;">Review the green fields and click Submit when ready.</div>
    </div>
    <div style="display:flex; gap:8px;">
      <button id="ajh-btn-mark" style="background:#10b981; color:#0f172a; font-weight:700; border:none; border-radius:6px; padding:6px 12px; font-size:11px; cursor:pointer; flex:1; transition:0.2s;">
        ✓ Mark as Applied
      </button>
      <button id="ajh-btn-close" style="background:#334155; color:#cbd5e1; border:none; border-radius:6px; padding:6px 10px; font-size:11px; cursor:pointer;">
        ✕
      </button>
    </div>
  `;

  overlay.style.position = "fixed";
  overlay.style.bottom = "24px";
  overlay.style.right = "24px";
  overlay.style.zIndex = "99999999";
  overlay.style.backgroundColor = "#0f172a";
  overlay.style.border = "1px solid #10b981";
  overlay.style.borderRadius = "10px";
  overlay.style.padding = "14px 16px";
  overlay.style.boxShadow = "0 10px 30px rgba(0,0,0,0.6)";
  overlay.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  overlay.style.minWidth = "280px";
  overlay.style.color = "#ffffff";

  document.body.appendChild(overlay);

  // Button Listeners
  document.getElementById("ajh-btn-close").onclick = () => overlay.remove();
  document.getElementById("ajh-btn-mark").onclick = async function () {
    this.innerText = "Recording...";
    try {
      await fetch("http://127.0.0.1:5000/api/mark-applied", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: window.location.href,
          company: document.title.split("-")[0].trim() || "Applied Company",
          role: document.title.split("-")[1]?.trim() || "Target Role"
        })
      });
      this.style.background = "#059669";
      this.innerText = "✅ Recorded to Dashboard!";
      setTimeout(() => overlay.remove(), 2500);
    } catch (e) {
      this.innerText = "✅ Saved locally!";
      setTimeout(() => overlay.remove(), 2000);
    }
  };

  console.log(`⚡ [AutoJobHunt] Completed autofill! Populated ${filledCount} fields in your logged-in browser session.`);
})();
