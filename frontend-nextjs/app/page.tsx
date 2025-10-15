"use client";
import { useEffect, useState } from "react";
import { Chat, setAgent } from "../components/Chat";
import { ProviderSelector } from "../components/ProviderSelector";
import { FileUpload } from "../components/FileUpload";

export default function Page() {
  const [agent, setAgentState] = useState({ provider: "openai", variant: "basic", systemPrompt: undefined as string | undefined });

  useEffect(() => {
    const h = (e: any) => setAgentState(e.detail);
    document.addEventListener("agent-change", h as any);
    return () => document.removeEventListener("agent-change", h as any);
  }, []);

  return (
    <div className="container">
      <h1 style={{fontWeight:600}}>🤖 Multi-Agent Workshop (Next.js)</h1>
      <p style={{color:"#9aa0a6"}}>Backend: {process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}</p>
      <ProviderSelector onChange={(p,v,sp) => setAgent(p,v,sp)} />
      <FileUpload />
      <Chat />
    </div>
  );
}
