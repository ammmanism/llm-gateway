"use client";

import { Activity } from "lucide-react";

const providers = [
  { name: "OpenAI", status: "healthy", latency: 450, errorRate: 0.1 },
  { name: "Anthropic", status: "healthy", latency: 520, errorRate: 0.05 },
  { name: "DeepSeek", status: "healthy", latency: 310, errorRate: 0.2 },
  { name: "Groq", status: "healthy", latency: 120, errorRate: 0.0 },
  { name: "Gemini", status: "degraded", latency: 850, errorRate: 4.2 },
];

export function ProviderHealth() {
  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-sm font-medium text-gray-400">Provider Health (EWMA)</h2>
        <Activity className="w-4 h-4 text-cyan-400" />
      </div>

      <div className="flex-1 overflow-auto pr-2">
        <div className="space-y-4">
          {providers.map((p) => (
            <div key={p.name} className="flex items-center justify-between bg-white/5 rounded-xl p-3 border border-white/5">
              <div className="flex items-center gap-3">
                <div className="relative flex h-3 w-3">
                  {p.status === "healthy" ? (
                    <>
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-brand-500"></span>
                    </>
                  ) : p.status === "degraded" ? (
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span>
                  ) : (
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                  )}
                </div>
                <span className="font-semibold text-sm">{p.name}</span>
              </div>
              <div className="flex items-center gap-4 text-xs font-medium tabular-nums text-gray-400">
                <div className="flex flex-col items-end">
                  <span>{p.latency}ms</span>
                </div>
                <div className="flex flex-col items-end min-w-[3rem]">
                  <span className={p.errorRate > 1 ? "text-yellow-500" : ""}>{p.errorRate.toFixed(1)}% err</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
