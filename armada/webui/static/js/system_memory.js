document.getElementById('mc-system-memory-open').addEventListener('click', () => {
  document.getElementById('mc-system-memory-dialog').showModal();
});

document.getElementById('mc-system-memory-file').addEventListener('click', async ({currentTarget: button}) => {
  const status = document.getElementById('mc-system-memory-status');
  button.disabled = true;
  status.textContent = '';
  try {
    const response = await fetch('/api/reveal-system-memory', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}',
    });
    const result = await response.json();
    if (!result.ok) throw Error(result.error || 'Could not locate the memory file.');
  } catch (error) {
    status.textContent = 'Could not show the memory file: ' + error.message;
  } finally {
    button.disabled = false;
  }
});
