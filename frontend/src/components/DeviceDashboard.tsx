"use client";

import { useState } from "react";
import { Search, Monitor, Cpu, HardDrive, Activity, Network, CheckCircle2 } from "lucide-react";

interface Device {
  hostname: string;
  ip: string;
  os: string;
  cpu: number;
  ram: number;
  storage: number;
  vpn: "Connected" | "Disconnected";
  health: "Healthy" | "Degraded" | "Offline";
  lastSync: string;
}

const mockDevices: Device[] = [
  { hostname: "JP-TOK-EDG-001", ip: "10.142.34.8", os: "Windows 11 Enterprise (v23H2)", cpu: 82, ram: 74, storage: 65, vpn: "Connected", health: "Degraded", lastSync: "3 mins ago" },
  { hostname: "US-NSH-LPT-284", ip: "10.120.45.102", os: "Windows 11 Enterprise (v22H2)", cpu: 18, ram: 45, storage: 38, vpn: "Connected", health: "Healthy", lastSync: "12 mins ago" },
  { hostname: "EU-BRU-SRV-049", ip: "10.88.12.3", os: "Windows Server 2022", cpu: 58, ram: 88, storage: 72, vpn: "Connected", health: "Healthy", lastSync: "Just now" },
  { hostname: "AP-SGP-LPT-105", ip: "10.200.74.52", os: "macOS Sonoma", cpu: 0, ram: 0, storage: 0, vpn: "Disconnected", health: "Offline", lastSync: "3 hours ago" }
];

export default function DeviceDashboard() {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredDevices = mockDevices.filter(dev => 
    dev.hostname.toLowerCase().includes(searchTerm.toLowerCase()) || dev.ip.includes(searchTerm)
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-gray-200">
        <div>
          <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <Monitor className="w-5 h-5 text-brand-red" />
            Enterprise Devices
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Status monitoring checklist of active endpoint agents.
          </p>
        </div>

        <div className="relative flex items-center bg-white border border-gray-200 rounded-lg px-3 py-1.5 w-60 shadow-sm">
          <Search className="w-3.5 h-3.5 text-gray-400 mr-2" />
          <input 
            type="text" 
            placeholder="Search hostname..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-transparent border-none outline-none text-xs text-gray-700 w-full"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredDevices.map(dev => (
          <div key={dev.hostname} className="card p-5 bg-white border border-gray-250 space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-sm font-bold text-gray-850 flex items-center gap-1.5">{dev.hostname}</h3>
                <span className="text-[10px] text-gray-400 font-mono block mt-0.5">{dev.os}</span>
              </div>
              <span className={`badge ${
                dev.health === "Healthy" ? "badge-healthy" : 
                dev.health === "Degraded" ? "badge-degraded" : "badge-unhealthy"
              }`}>{dev.health}</span>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center bg-gray-50 p-2.5 rounded-lg text-xs font-semibold text-gray-650">
              <div>
                <span className="text-[9px] text-gray-400 block font-bold">CPU</span>
                <span className="text-gray-850 block mt-0.5">{dev.health === "Offline" ? "—" : `${dev.cpu}%`}</span>
              </div>
              <div className="border-x border-gray-200">
                <span className="text-[9px] text-gray-400 block font-bold">RAM</span>
                <span className="text-gray-850 block mt-0.5">{dev.health === "Offline" ? "—" : `${dev.ram}%`}</span>
              </div>
              <div>
                <span className="text-[9px] text-gray-400 block font-bold">STORAGE</span>
                <span className="text-gray-850 block mt-0.5">{dev.health === "Offline" ? "—" : `${dev.storage}%`}</span>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-100 flex justify-between text-[10px] text-gray-450 font-semibold">
              <span className="flex items-center gap-1"><Network className="w-3.5 h-3.5" /> VPN: <strong className={dev.vpn === "Connected" ? "text-green-600" : "text-gray-500"}>{dev.vpn}</strong></span>
              <span>Sync: {dev.lastSync}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
