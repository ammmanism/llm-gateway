"use client";

import { BarChart2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const data = [
  { time: "00:00", openai: 450, anthropic: 520, deepseek: 310, groq: 120, gemini: 400 },
  { time: "04:00", openai: 420, anthropic: 510, deepseek: 300, groq: 110, gemini: 390 },
  { time: "08:00", openai: 550, anthropic: 580, deepseek: 350, groq: 150, gemini: 450 },
  { time: "12:00", openai: 800, anthropic: 700, deepseek: 400, groq: 180, gemini: 550 },
  { time: "16:00", openai: 600, anthropic: 620, deepseek: 320, groq: 140, gemini: 480 },
  { time: "20:00", openai: 480, anthropic: 530, deepseek: 310, groq: 130, gemini: 420 },
];

export function LatencyHeatmap() {
  return (
    <div className="glass-panel p-6 flex flex-col h-[300px]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-gray-400">Latency Distribution (ms)</h2>
        <BarChart2 className="w-4 h-4 text-purple-400" />
      </div>
      
      <div className="flex-1 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <XAxis dataKey="time" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip 
              cursor={{ fill: 'rgba(255,255,255,0.05)' }}
              contentStyle={{ backgroundColor: '#18181b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '0.75rem' }}
            />
            <Bar dataKey="openai" fill="#10b981" radius={[4, 4, 0, 0]} stackId="a" />
            <Bar dataKey="anthropic" fill="#8b5cf6" radius={[4, 4, 0, 0]} stackId="a" />
            <Bar dataKey="deepseek" fill="#3b82f6" radius={[4, 4, 0, 0]} stackId="a" />
            <Bar dataKey="groq" fill="#f43f5e" radius={[4, 4, 0, 0]} stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
