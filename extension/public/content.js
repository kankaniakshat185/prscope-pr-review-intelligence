(function() {
  const repoUrl = window.location.href;
  const match = repoUrl.match(/github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/);
  let prUrl = "";
  if (match) {
    prUrl = `?owner=${match[1]}&repo=${match[2]}&pr=${match[3]}`;
  }
  const newSrc = chrome.runtime.getURL(`index.html${prUrl}`);

  if (document.getElementById("pr-copilot-sidebar")) {
    const sidebar = document.getElementById("pr-copilot-sidebar");
    const iframe = sidebar.querySelector("iframe");
    if (iframe && iframe.src !== newSrc) {
      iframe.src = newSrc;
    }
    sidebar.style.transform = "translateX(0)";
    const body = document.querySelector("body");
    if (body) body.style.paddingRight = "400px";
    const peekBar = document.getElementById("pr-copilot-peekbar");
    if (peekBar) peekBar.style.display = "none";
    return;
  }

  // Create a container for the sidebar
  const sidebar = document.createElement("div");
  sidebar.id = "pr-copilot-sidebar";
  
  Object.assign(sidebar.style, {
    position: "fixed",
    top: "0",
    right: "0",
    width: "400px",
    height: "100vh",
    backgroundColor: "#010409",
    borderLeft: "1px solid #30363d",
    zIndex: "999999",
    boxShadow: "-2px 0 8px rgba(0,0,0,0.5)"
  });

  // Load the React app in an iframe
  const iframe = document.createElement("iframe");
  iframe.src = newSrc;
  iframe.allow = "clipboard-write";
  
  Object.assign(iframe.style, {
    width: "100%",
    height: "100%",
    border: "none",
  });

  sidebar.appendChild(iframe);
  document.body.appendChild(sidebar);
  
  // Create an invisible overlay for the peek bar when collapsed
  const peekBar = document.createElement("div");
  peekBar.id = "pr-copilot-peekbar";
  Object.assign(peekBar.style, {
    position: "absolute",
    left: "0",
    top: "0",
    width: "10px",
    height: "100%",
    cursor: "pointer",
    display: "none",
    zIndex: "10",
    backgroundColor: "transparent",
    borderLeft: "2px solid #58a6ff"
  });
  
  // On hover over peek bar, add a small highlight
  peekBar.addEventListener("mouseenter", () => { peekBar.style.backgroundColor = "rgba(88, 166, 255, 0.2)"; });
  peekBar.addEventListener("mouseleave", () => { peekBar.style.backgroundColor = "transparent"; });
  
  sidebar.appendChild(peekBar);
  
  // Add transition to sidebar
  sidebar.style.transition = "transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)";
  
  const body = document.querySelector("body");
  if (body) {
    body.style.transition = "padding-right 0.3s cubic-bezier(0.16, 1, 0.3, 1)";
    body.style.paddingRight = "400px";
  }
  
  let isCollapsed = false;
  peekBar.addEventListener("click", () => {
    isCollapsed = false;
    sidebar.style.transform = "translateX(0)";
    if (body) body.style.paddingRight = "400px";
    peekBar.style.display = "none";
  });


  // Listen for clipboard copy requests from the iframe
  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "COPY_TO_CLIPBOARD") {
      navigator.clipboard.writeText(event.data.text).catch(err => {
        const textarea = document.createElement("textarea");
        textarea.value = event.data.text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      });
    } else if (event.data && event.data.type === "TOGGLE_COLLAPSE") {
      isCollapsed = true;
      sidebar.style.transform = "translateX(390px)";
      if (body) body.style.paddingRight = "10px";
      peekBar.style.display = "block";
    } else if (event.data && event.data.type === "REQUEST_THEME") {
      sendTheme();
    }
  });

  function sendTheme() {
    const computed = window.getComputedStyle(document.documentElement);
    let style = ":root {\n";
    // Iterate over explicitly defined variables or all styles
    for (let i = 0; i < computed.length; i++) {
      const prop = computed[i];
      if (prop.startsWith('--color-') || prop.startsWith('--bgColor-') || prop.startsWith('--fgColor-') || prop.startsWith('--borderColor-')) {
        style += `${prop}: ${computed.getPropertyValue(prop)};\n`;
      }
    }
    style += "}";
    iframe.contentWindow.postMessage({ type: "SYNC_THEME", style }, "*");
  }
  
  // Also send theme on load and on DOM mutation
  iframe.onload = () => {
    sendTheme();
  };
  
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === 'attributes' && (m.attributeName === 'data-color-mode' || m.attributeName === 'data-dark-theme' || m.attributeName === 'data-light-theme')) {
        sendTheme();
      }
    }
  });
  observer.observe(document.documentElement, { attributes: true });
})();
