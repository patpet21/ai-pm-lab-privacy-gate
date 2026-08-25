(() => {
  const status = document.getElementById('status');
  const query = window.location.search || '';
  const params = new URLSearchParams(query);
  const hasOAuthResponse = params.has('code') || params.has('error');

  if (!hasOAuthResponse) {
    if (status) {
      status.textContent = 'Asana callback is online and ready. Start the connection from the PrivacyGate desktop app.';
    }
    return;
  }

  const target = `http://127.0.0.1:8768/asana${query}`;
  window.location.replace(target);
  window.setTimeout(() => {
    if (status) {
      status.textContent = 'If PrivacyGate did not complete automatically, make sure the desktop app is still running and try Connect again.';
    }
  }, 2500);
})();
