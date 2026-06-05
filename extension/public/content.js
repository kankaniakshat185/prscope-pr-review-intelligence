(function() {
  if (document.getElementById("pr-copilot-sidebar")) return;

  // Create a container for the sidebar
  const sidebar = document.createElement("div");
  sidebar.id = "pr-copilot-sidebar";
  
  Object.assign(sidebar.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "400px",
    height: "100vh",
    backgroundColor: "#0d1117",
    borderLeft: "1px solid #30363d",
    zIndex: "999999",
    boxShadow: "-2px 0 8px rgba(0,0,0,0.5)"
  });

  // Load the React app in an iframe
  const iframe = document.createElement("iframe");
  
  // Pass the current URL as a parameter so the app knows which PR to analyze
  const repoUrl = window.location.href;
  const match = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
  let prUrl = "";
  if (match) {
    prUrl = `?owner=${match[1]}&repo=${match[2]}&pr=${match[3]}`;
  }

  iframe.src = chrome.runtime.getURL(`index.html${prUrl}`);
  
  Object.assign(iframe.style, {
    width: "100%",
    height: "100%",
    border: "none",
  });

  sidebar.appendChild(iframe);
  document.body.appendChild(sidebar);
  
  // Adjust GitHub's layout to accommodate the sidebar
  const body = document.querySelector("body");
  if (body) {
    body.style.paddingRight = "400px";
  }
})();
