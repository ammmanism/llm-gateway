"use client";

import { Users } from "lucide-react";

const tenants = [
  { id: "t_corp_a", name: "Acme Corp", requests: "1.2M", saved: 4520, hitRate: 68 },
  { id: "t_corp_b", name: "GlobalTech", requests: "850K", saved: 3100, hitRate: 72 },
  { id: "t_startup", name: "Fast Startup", requests: "420K", saved: 1250, hitRate: 45 },
  { id: "t_internal", name: "Internal Tools", requests: "150K", saved: 890, hitRate: 85 },
];

export function TenantUsage() {
  return (
    <div className="glass-panel p-6 flex flex-col h-full">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-sm font-medium text-gray-400">Top Tenants</h2>
        <Users className="w-4 h-4 text-blue-400" />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-500 uppercase bg-transparent border-b border-cardBorder">
            <tr>
              <th className="px-4 py-3 font-medium">Tenant</th>
              <th className="px-4 py-3 font-medium text-right">Requests</th>
              <th className="px-4 py-3 font-medium text-right">Saved</th>
              <th className="px-4 py-3 font-medium text-right">Cache Hit</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id} className="border-b border-cardBorder/50 last:border-0 hover:bg-white/5 transition-colors">
                <td className="px-4 py-4 font-medium">{t.name}</td>
                <td className="px-4 py-4 text-right tabular-nums text-gray-400">{t.requests}</td>
                <td className="px-4 py-4 text-right tabular-nums text-brand-500 font-medium">${t.saved.toLocaleString()}</td>
                <td className="px-4 py-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <span className="tabular-nums">{t.hitRate}%</span>
                    <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${t.hitRate > 60 ? 'bg-brand-500' : 'bg-yellow-500'}`}
                        style={{ width: `${t.hitRate}%` }}
                      ></div>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
