import { CostSavingsCard } from "@/components/CostSavingsCard";
import { CacheHitGauge } from "@/components/CacheHitGauge";
import { ProviderHealth } from "@/components/ProviderHealth";
import { LatencyHeatmap } from "@/components/LatencyHeatmap";
import { TenantUsage } from "@/components/TenantUsage";

export default function Home() {
  return (
    <div className="flex flex-col gap-6 w-full animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      {/* Top Row: Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <CostSavingsCard />
        </div>
        <div className="lg:col-span-1">
          <CacheHitGauge />
        </div>
        <div className="lg:col-span-1">
          <ProviderHealth />
        </div>
      </div>

      {/* Bottom Row: Charts & Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <LatencyHeatmap />
        </div>
        <div className="lg:col-span-1">
          <TenantUsage />
        </div>
      </div>
    </div>
  );
}