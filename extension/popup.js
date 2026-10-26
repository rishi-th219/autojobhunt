document.getElementById("fill-btn").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab && tab.id) {
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const s = document.createElement("script");
        s.src = "http://127.0.0.1:5000/autofill.js?t=" + Date.now();
        document.body.appendChild(s);
      }
    });
    window.close();
  }
});
