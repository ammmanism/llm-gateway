"use client";

import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { Zap } from "lucide-react";

export function CacheHitGauge() {
  const [hitRate, setHitRate] = useState(65.4);

  // Mock fluctuation
  useEffect(() => {
    const interval = setInterval(() => {
      setHitRate(prev => {
        const delta = (Math.random() - 0.5) * 2;
        const next = prev + delta;
        return Math.min(Math.max(next, 0), 100);
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const data = [
    { name: "Hits", value: hitRate },
    { name: "Misses", value: 100 - hitRate },
  ];

  const getColor = (rate: number) => {
    if (rate >= 75) return "#10b981"; // Emerald
    if (rate >= 50) return "#f59e0b"; // Amber
    return "#ef4444"; // Red
  };

  const color = getColor(hitRate);

  return (
    <div className="glass-panel p-6 flex flex-col items-center justify-center relative">
      <div className="absolute top-6 left-6 flex items-center justify-between w-[calc(100%-3rem)]">
        <h2 className="text-sm font-medium text-gray-400">Cache Hit Rate</h2>
        <Zap className="w-4 h-4 text-yellow-400" />
      </div>

      <div className="h-48 w-full mt-8 relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius="75%"
              outerRadius="100%"
              paddingAngle={0}
              dataKey="value"
              stroke="none"
              animationDuration={1000}
            >
              <Cell fill={color} />
              <Cell fill="rgba(255,255,255,0.05)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
          <div className="text-4xl font-black tabular-nums tracking-tighter" style={{ color }}>
            {hitRate.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 font-medium uppercase tracking-wider mt-1">
            Overall Average
          </div>
        </div>
      </div>
    </div>
  );
}
