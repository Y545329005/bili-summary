// Bili 投资研究总结 — Background Service Worker
// Keeps track of the API server status and provides badge info.

const API_BASE = 'http://127.0.0.1:8765';

chrome.runtime.onInstalled.addListener(() => {
  console.log('Bili 投资研究总结 扩展已安装');
});

// Optional: listen for messages from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'check_server') {
    fetch(`${API_BASE}/api/stats`)
      .then(r => r.json())
      .then(data => sendResponse({ online: true, ...data }))
      .catch(() => sendResponse({ online: false }));
    return true; // async response
  }
});
