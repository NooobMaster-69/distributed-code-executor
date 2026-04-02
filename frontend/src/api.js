const API_BASE = '';

export async function submitCode(code, language, timeout) {
  const res = await fetch(`${API_BASE}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, language, timeout }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error (${res.status})`);
  }

  return res.json();
}

export async function getStatus(jobId) {
  const res = await fetch(`${API_BASE}/status/${jobId}`);

  if (!res.ok) {
    throw new Error(`Failed to fetch status (${res.status})`);
  }

  return res.json();
}

export async function getResult(jobId) {
  const res = await fetch(`${API_BASE}/result/${jobId}`);

  if (!res.ok) {
    throw new Error(`Failed to fetch result (${res.status})`);
  }

  return res.json();
}
