"use client";
import { useState } from "react";

export function ProviderSelector(props: {
  onChange: (p: string, v: "basic"|"custom"|"tool", sp?: string) => void;
}) {
  const [provider, setProvider] = useState("openai");
  const [variant, setVariant] = useState<"basic"|"custom"|"tool">("basic");
  const [systemPrompt, setSystemPrompt] = useState("You are a helpful assistant.");

  return (
    <div className="panel" style={{marginBottom: 16}}>
      <div className="row" style={{gap: 16}}>
        <select className="input" value={provider} onChange={e => { setProvider(e.target.value); props.onChange(e.target.value, variant, systemPrompt); }}>
          {["openai","anthropic","google","ollama","langchain","langgraph","smolagent","deepseek"].map(p => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <select className="input" value={variant} onChange={e => {
          const v = e.target.value as "basic"|"custom"|"tool";
          setVariant(v); props.onChange(provider, v, systemPrompt);
        }}>
          <option value="basic">basic</option>
          <option value="custom">custom</option>
          <option value="tool">tool</option>
        </select>
      </div>
      {variant === "custom" && (
        <textarea className="input" style={{marginTop:12}} rows={4} value={systemPrompt} onChange={e => { setSystemPrompt(e.target.value); props.onChange(provider, variant, e.target.value); }} />
      )}
    </div>
  );
}
