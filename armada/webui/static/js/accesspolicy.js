(() => {
  const root = document.querySelector('.mc-access-policy');
  if (!root) return;
  const lines = el => el.value.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  const status = root.querySelector('[data-policy-status]');
  root.querySelectorAll('[data-save-tool-names]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('[data-inventory-connector]');
    send(button, '/api/save-tool-inventory', {connector:row.dataset.inventoryConnector,
      names:lines(row.querySelector('[data-tool-names]'))});
  }));
  async function send(button, url, body) {
    button.disabled = true;
    status.textContent = 'Saving…';
    try {
      const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'Could not save access.');
      location.reload();
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }
  root.querySelector('[data-save-agent-policy]').addEventListener('click', event => {
    const tools = {};
    root.querySelectorAll('[data-tool-connector]').forEach(row => {
      if (row.querySelector('[data-limit-tools]').checked) tools[row.dataset.toolConnector] = {
        allow:lines(row.querySelector('[data-allow]')), deny:lines(row.querySelector('[data-deny]'))};
    });
    send(event.target, '/api/save-access-policy', {agent:root.dataset.agent, policy:{tool_policy:tools,
      write_scope:root.querySelector('[data-limit-writes]').checked ? lines(root.querySelector('[data-write-scope]')) : null}});
  });
  root.querySelector('[data-save-realm-policy]').addEventListener('click', event => {
    const tools = {};
    root.querySelectorAll('[data-default-connector]').forEach(row => {
      const deny = lines(row); if (deny.length) tools[row.dataset.defaultConnector] = {deny};
    });
    send(event.target, '/api/save-access-policy', {policy:{tool_policy:tools,
      read_only:lines(root.querySelector('[data-read-only]')), policy_builder:root.querySelector('[data-policy-builder]').value.trim()}});
  });
  root.querySelector('[data-refresh-tools]').addEventListener('click', event =>
    send(event.target, '/api/refresh-tool-inventory', {agent:root.dataset.agent, provider:root.dataset.provider}));
})();
