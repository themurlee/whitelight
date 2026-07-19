const API_BASE = (typeof window !== "undefined" && window.WHITELIGHT_API_BASE) || "http://localhost:8787";

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}
