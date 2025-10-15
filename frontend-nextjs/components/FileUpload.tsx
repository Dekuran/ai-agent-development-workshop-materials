"use client";
import { useState } from "react";
import { upload } from "../lib/api";

export function FileUpload() {
  const [status, setStatus] = useState<string>("");

  return (
    <div className="panel" style={{marginBottom:16}}>
      <div className="row">
        <input className="input" type="file" onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          setStatus("Uploading...");
          try {
            await upload(f);
            setStatus(\`Uploaded: \${f.name}\`);
          } catch (e: any) {
            setStatus(e.message || "Upload failed");
          }
        }} />
        <span className="badge">{status || "No file selected"}</span>
      </div>
    </div>
  );
}
