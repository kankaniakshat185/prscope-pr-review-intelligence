chrome.action.onClicked.addListener((tab) => {
  if (tab.url && tab.url.includes("github.com") && tab.url.includes("/pull/")) {
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"]
    });
  }
});
