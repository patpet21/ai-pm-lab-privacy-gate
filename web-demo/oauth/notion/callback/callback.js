(() => {
  const status = document.getElementById('status');
  const query = window.location.search || '';
  const target = `http://127.0.0.1:8770/notion${query}`;
  window.location.replace(target);
  window.setTimeout(() => {
    if (status) {
      status.textContent = 'If PrivacyGate did not complete automatically, make sure the desktop app is still running and try Connect again.';
    }
  }, 2500);
})();
