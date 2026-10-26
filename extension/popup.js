document.getElementById("fill-btn").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.id) {
    const btn = document.getElementById("fill-btn");
    btn.innerText = "Filling form...";

    chrome.tabs.sendMessage(tab.id, { action: "autofill_now" }, (response) => {
      if (chrome.runtime.lastError || !response) {
        // Fallback execute
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"]
        }, () => {
          setTimeout(() => {
            chrome.tabs.sendMessage(tab.id, { action: "autofill_now" }, (res2) => {
              if (res2) {
                btn.innerText = `✓ ${res2.filled} Fields Filled!`;
                btn.style.background = "#059669";
                btn.style.color = "#ffffff";
              } else {
                btn.innerText = "✓ Autofill Executed!";
              }
            });
          }, 300);
        });
      } else {
        btn.innerText = `✓ ${response.filled} Fields Filled!`;
        btn.style.background = "#059669";
        btn.style.color = "#ffffff";
        setTimeout(() => window.close(), 1500);
      }
    });
  }
});
