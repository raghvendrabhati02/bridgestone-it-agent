"use client";

import { BarChart3 } from "lucide-react";

export default function AnalyticsView() {
  return (
    <div className="p-6 space-y-6">
      <div className="pb-4 border-b border-gray-200">
        <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-brand-red" />
          IT Support Analytics
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Standardised performance rates and volume metrics.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[
          { label: "AI Resolution Rate", val: "91.4%" },
          { label: "Human Escalation Rate", val: "8.6%" },
          { label: "Avg Resolution Time", val: "1m 24s" }
        ].map(kpi => (
          <div key={kpi.label} className="card p-5 bg-white border border-gray-250 text-center space-y-1 shadow-sm">
            <span className="text-[10px] text-gray-400 font-bold block uppercase tracking-wider">{kpi.label}</span>
            <span className="text-2xl font-extrabold text-gray-850 block">{kpi.val}</span>
          </div>
        ))}
      </div>

      {/* Issues list */}
      <div className="card p-5 bg-white border border-gray-250 space-y-4 shadow-sm">
        <span className="section-header block border-b border-gray-100 pb-2">Top 5 Issue Categories</span>
        <div className="divide-y divide-gray-150 text-xs font-semibold text-gray-650">
          {[
            { cat: "Account Lockouts & Password Resets", percentage: "31%" },
            { cat: "VPN Gateway Connection Resets", percentage: "24%" },
            { cat: "Software Deployment Failures (SAP GUI, 7-Zip)", percentage: "19%" },
            { cat: "Outlook Caching & Mail Sync", percentage: "14%" },
            { cat: "Network Printer Mapping", percentage: "12%" }
          ].map((item, idx) => (
            <div key={item.cat} className="py-2.5 flex justify-between items-center">
              <span>{idx + 1}. {item.cat}</span>
              <span className="badge badge-assigned font-bold">{item.percentage}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
