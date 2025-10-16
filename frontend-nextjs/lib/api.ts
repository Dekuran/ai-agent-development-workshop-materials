const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8050";

export type Message = { role: "system" | "user" | "assistant"; content: string };

export async function chat(provider: string, variant: "basic"|"custom"|"tool", messages: Message[], systemPrompt?: string) {
  const r = await fetch(\`\${BASE}/chat/\${provider}\`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_variant: variant, messages, system_prompt: systemPrompt }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ content: string }>;
}

export async function upload(file: File) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const r = await fetch(\`\${BASE}/upload\`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
