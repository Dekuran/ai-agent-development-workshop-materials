"use client";
import { useState } from "react";
import { chat, type Message } from "../lib/api";

export function Chat() {
  const [provider, setProvider] = useState("openai");
  const [variant, setVariant] = useState<"basic"|"custom"|"tool">("basic");
  const [systemPrompt, setSystemPrompt] = useState<string | undefined>(undefined);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    if (!input || busy) return;
    const next = [...messages, { role: "user", content: input } as Message];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const r = await chat(provider, variant, next, systemPrompt);
      setMessages([...next, { role: "assistant", content: r.content }]);
    } catch (e: any) {
      setMessages([...next, { role: "assistant", content: e.message || "Error" }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <div className="row" style={{marginBottom: 12}}>
        <span className="badge">Provider: {provider}</span>
        <span className="badge">Variant: {variant}</span>
      </div>
      <div className="chat" style={{minHeight: 240}}>
        {messages.map((m,i) => (
          <div key={i} className={\`bubble \${m.role}\`}>{m.content}</div>
        ))}
      </div>
      <div className="row" style={{marginTop: 12}}>
        <input className="input" value={input} onChange={e => setInput(e.target.value)} placeholder="Type a message" onKeyDown={e => { if (e.key === "Enter") send(); }} />
        <button className="button" onClick={send} disabled={busy}>Send</button>
      </div>
    </div>
  );
}

export function setAgent(p: string, v: "basic"|"custom"|"tool", sp?: string) {
  // This is a tiny cross-component mediator in lieu of global store to keep scaffold simple.
  // In a real app, use Zustand/Context. Here we expose setters via document events.
  const ev = new CustomEvent("agent-change", { detail: { provider: p, variant: v, systemPrompt: sp } });
  document.dispatchEvent(ev);
}
