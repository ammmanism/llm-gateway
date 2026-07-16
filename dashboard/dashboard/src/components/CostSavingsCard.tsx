"use client";

import { useEffect, useState } from "react";
import { TrendingDown, DollarSign } from "lucide-react";

export function CostSavingsCard() {
  const [savings, setSavings] = useState(0);

  // Mocking real-time updates for demonstration
  useEffect(() => {
    const interval = setInterval(() => {
      setSavings(prev => prev + Math.random() * 0.5 + 0.1);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="glass-panel p-6 flex flex-col justify-between relative overflow-hidden group">
      {/* Glow effect */}
      <div className="absolute -inset-0.5 bg-gradient-to-r from-brand-500 to-cyan-500 rounded-2xl opacity-20 group-hover:opacity-30 blur-2xl transition duration-1000"></div>
      
      <div className="relative z-10 flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-gray-400">Total Savings (30d)</h2>
        <div className="p-2 bg-brand-500/10 rounded-full">
          <TrendingDown className="w-4 h-4 text-brand-500" />
        </div>
      </div>
      
      <div className="relative z-10">
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold text-gray-400">$</span>
          <span className="text-5xl font-black tabular-nums tracking-tighter">
            {savings.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <p className="text-xs text-brand-500 mt-2 font-medium flex items-center gap-1">
          <DollarSign className="w-3 h-3" />
          Saved vs naive GPT-4o routing
        </p>
      </div>
    </div>
  );
}