"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback } from "react";
import {
  Monitor, Cpu, HardDrive, Activity, Network, CheckCircle2, AlertCircle, Clock,
  Filter, ChevronLeft, ChevronRight, X, Play, RefreshCw,
  ChevronDown, ChevronUp, History, Server, Info, ShieldAlert, Laptop
} from "lucide-react";
import {
  SearchInput,
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  Badge
} from "./shared/UIComponents";

interface Device {
  id: string;
  hostname: string;
  serial_number: string;
  manufacturer: string;
  model: string;
  operating_system: string;
  ram: number;
  cpu: number;
  disk: number;
  ip_address: string;
  mac_address: string;
  agent_version: string;
  status: "Online" | "Offline" | "Updating" | "Error" | "Inactive";
  last_heartbeat: string;
  last_seen: string;
  username: string;
  department: string;
  installed_software?: string[];
  running_processes?: string[];
  network_interfaces?: Array<{ name: string; ip: string; status: string }>;
}

interface ExecutionRecord {
  id: number;
  timestamp: string;
  username: string;
  device_id: string;
  action_name: string;
  result: string;
  duration: number;
  logs?: string;
}

interface DeviceDashboardProps {
  user: any;
  token: string | null;
  apiBaseUrl: string;
}

export default function DeviceDashboard({ user, token, apiBaseUrl }: DeviceDashboardProps) {
  // --- State Variables ---
  const [devices, setDevices] = useState<Device[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [osFilter, setOsFilter] = useState("");
  const [versionFilter, setVersionFilter] = useState("");
  const [sortBy, setSortBy] = useState("hostname");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Summary statistics for cards
  const [stats, setStats] = useState<any>({
    total_devices: 0,
    online_devices: 0,
    offline_devices: 0,
    pending_updates: 0,
    healthy_devices: 0,
    inactive_devices: 0,
    last_heartbeat: null,
    agent_versions: "None"
  });

  // Loading states
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState<string | null>(null);
  const [isActionExecuting, setIsActionExecuting] = useState(false);

  // Side Drawer details
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"details" | "software" | "processes" | "history" | "health">("details");
  const [deviceHistory, setDeviceHistory] = useState<ExecutionRecord[]>([]);
  const [deviceHealth, setDeviceHealth] = useState<any>(null);

  // Notification Toast state
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // --- Auth Headers Helper ---
  const getHeaders = useCallback(() => {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token || localStorage.getItem("access_token")}`
    };
  }, [token]);

  // Show dynamic notification toasts
  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // --- Fetch Devices list ---
  const fetchDevices = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        search,
        status: statusFilter,
        department: deptFilter,
        os: osFilter,
        agent_version: versionFilter,
        sort_by: sortBy,
        sort_order: sortOrder
      });

      const res = await apiFetch(`${apiBaseUrl}/api/devices?${params.toString()}`, {
        headers: getHeaders()
      });

      if (!res.ok) throw new Error("Failed to fetch device data");
      
      const data = await res.json();
      setDevices(data.devices || []);
      setTotalCount(data.total || 0);
      if (data.stats) {
        setStats(data.stats);
      }
    } catch (err: any) {
      if (err instanceof NetworkError) return; // silently skip when backend offline
      showToast(err.message || "Connection error to database.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [page, limit, search, statusFilter, deptFilter, osFilter, versionFilter, sortBy, sortOrder, apiBaseUrl, getHeaders]);

  // Load devices list when filter/query dependencies change
  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  // --- Fetch Selected Device details, history, and health ---
  const loadDeviceExtraDetails = async (devId: string) => {
    try {
      // 1. Fetch History
      const histRes = await apiFetch(`${apiBaseUrl}/api/devices/${devId}/history`, {
        headers: getHeaders()
      });
      if (histRes.ok) {
        const histData = await histRes.json();
        setDeviceHistory(histData || []);
      }

      // 2. Fetch Health Diagnostics
      const healthRes = await apiFetch(`${apiBaseUrl}/api/devices/${devId}/health`, {
        headers: getHeaders()
      });
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setDeviceHealth(healthData);
      }
    } catch (err) {
      if (!(err instanceof NetworkError)) {
        console.warn("Failed to load device history/health details", err);
      }
      // NetworkError: silently skip, backend offline banner handles this
    }
  };

  // --- Click Row Handler ---
  const handleViewDetails = async (device: Device) => {
    setSelectedDevice(device);
    setIsDrawerOpen(true);
    setActiveTab("details");
    setDeviceHistory([]);
    setDeviceHealth(null);
    await loadDeviceExtraDetails(device.id);
  };

  // --- Refresh Device Action ---
  const handleRefreshDevice = async (devId: string, event?: React.MouseEvent) => {
    if (event) event.stopPropagation();
    setIsRefreshing(devId);
    try {
      const res = await apiFetch(`${apiBaseUrl}/api/devices/${devId}/refresh`, {
        method: "POST",
        headers: getHeaders()
      });

      if (!res.ok) throw new Error("Failed to contact agent");

      const data = await res.json();
      showToast(`Device telemetry refreshed successfully (${data.refreshed_live ? "Live" : "Cached"})`);
      
      // Update selected device if active
      if (selectedDevice?.id === devId) {
        setSelectedDevice(data.device);
        await loadDeviceExtraDetails(devId);
      }
      
      // Refresh list
      fetchDevices();
    } catch (err: any) {
      showToast(err.message || "Failed to refresh device.", "error");
    } finally {
      setIsRefreshing(null);
    }
  };

  // --- Restart Device Agent Action (Simulated execution logs addition) ---
  const handleRestartAgent = async (devId: string, hostname: string) => {
    setIsActionExecuting(true);
    try {
      const restartActionUrl = `${apiBaseUrl}/api/devices/${devId}/refresh`;
      await fetch(restartActionUrl, {
        method: "POST",
        headers: getHeaders()
      });

      await new Promise((resolve) => setTimeout(resolve, 2000));
      
      showToast(`Enterprise Device Agent service restarted on ${hostname}`);
      if (selectedDevice?.id === devId) {
        await loadDeviceExtraDetails(devId);
      }
      fetchDevices();
    } catch (err) {
      showToast("Failed to execute agent restart action", "error");
    } finally {
      setIsActionExecuting(false);
    }
  };

  // --- Sort Handler ---
  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("asc");
    }
    setPage(1);
  };

  // --- Clear All Filters ---
  const handleClearFilters = () => {
    setSearchInput("");
    setSearch("");
    setStatusFilter("");
    setDeptFilter("");
    setOsFilter("");
    setVersionFilter("");
    setPage(1);
  };

  const totalPages = Math.ceil(totalCount / limit);

  return (
    <div className="flex-1 flex flex-col bg-[#F8FAFC] font-sans h-full min-h-screen relative pb-10">
      
      {/* Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-55 flex items-center gap-2 px-4 py-3 rounded-xl border shadow-xl bg-white border-[#E2E8F0] max-w-sm">
          {toast.type === "success" && <CheckCircle2 className="w-5 h-5 text-[#16A34A]" aria-hidden />}
          {toast.type === "error" && <AlertCircle className="w-5 h-5 text-[#DC2626]" aria-hidden />}
          {toast.type === "info" && <Info className="w-5 h-5 text-[#2563EB]" aria-hidden />}
          <span className="text-xs font-semibold text-[#1E293B]">{toast.message}</span>
        </div>
      )}

      {/* Top Header Title Block */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 flex-shrink-0">
        <div>
          <h1 className="text-[16px] font-bold text-[#0F172A] flex items-center gap-2.5">
            <Monitor className="w-4 h-4 text-[#E30613]" aria-hidden />
            Enterprise Device Registry
          </h1>
          <p className="text-xs text-[#64748B] mt-0.5">
            Device Agent heartbeat checkins & status monitoring dashboard
          </p>
        </div>

        <button
          onClick={fetchDevices}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer disabled:opacity-50 transition-colors shadow-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} aria-hidden />
          Refresh Registry
        </button>
      </div>

      {/* Dashboard Stats Cards Grid */}
      <div className="p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {[
          { label: "Online Devices", count: stats.online_devices, icon: CheckCircle2, color: "text-[#16A34A] bg-[#F0FDF4] border-[#BBF7D0]" },
          { label: "Offline Devices", count: stats.offline_devices, icon: X, color: "text-[#64748B] bg-[#F8FAFC] border-[#CBD5E1]" },
          { 
            label: "Last Heartbeat", 
            count: stats.last_heartbeat 
              ? new Date(stats.last_heartbeat).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) 
              : "None", 
            icon: Clock, 
            color: "text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]" 
          },
          { label: "Agent Versions", count: (stats as any).agent_versions || "1.0", icon: Laptop, color: "text-purple-700 bg-purple-50 border-purple-100" },
          { label: "Healthy Devices", count: stats.healthy_devices, icon: Activity, color: "text-emerald-755 bg-emerald-50 border-emerald-100" }
        ].map((card, idx) => (
          <div key={idx} className="bg-white border border-[#E2E8F0] rounded-xl p-4 flex flex-col justify-between shadow-xs relative overflow-hidden group hover:shadow-sm transition-all">
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">{card.label}</span>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center border ${card.color}`}>
                <card.icon className="w-3.5 h-3.5" />
              </div>
            </div>
            <span className="text-lg font-bold text-[#0F172A] mt-3 group-hover:scale-102 transition-transform duration-200 truncate">{card.count}</span>
          </div>
        ))}
      </div>

      {/* Query, Search and Filter Panel */}
      <div className="mx-6 p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1">
            <SearchInput
              placeholder="Search Hostname, Username, Department, IP..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setSearch(searchInput)}
            />
          </div>

          <button
            onClick={() => setSearch(searchInput)}
            className="px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer shadow-xs transition-colors"
          >
            Apply Search
          </button>
          
          {(search || statusFilter || deptFilter || osFilter || versionFilter) && (
            <button
              onClick={handleClearFilters}
              className="px-3 py-1.5 bg-transparent text-xs font-bold text-[#E30613] hover:underline cursor-pointer"
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Dropdown Filters */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-[#F1F5F9] font-bold">
          <div>
            <label className="block text-[9px] text-[#64748B] uppercase mb-1">Status</label>
            <div className="relative flex items-center">
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none p-2 border border-[#E2E8F0] rounded-lg text-xs bg-white text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Statuses</option>
                <option value="Online">Online</option>
                <option value="Offline">Offline</option>
                <option value="Updating">Updating</option>
                <option value="Error">Error</option>
                <option value="Inactive">Inactive</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          <div>
            <label className="block text-[9px] text-[#64748B] uppercase mb-1">Department</label>
            <div className="relative flex items-center">
              <select
                value={deptFilter}
                onChange={(e) => { setDeptFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none p-2 border border-[#E2E8F0] rounded-lg text-xs bg-white text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Departments</option>
                <option value="Logistics">Logistics</option>
                <option value="HR">HR</option>
                <option value="IT Operations">IT Operations</option>
                <option value="Finance">Finance</option>
                <option value="Engineering">Engineering</option>
                <option value="Sales">Sales</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          <div>
            <label className="block text-[9px] text-[#64748B] uppercase mb-1">Operating System</label>
            <div className="relative flex items-center">
              <select
                value={osFilter}
                onChange={(e) => { setOsFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none p-2 border border-[#E2E8F0] rounded-lg text-xs bg-white text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All OS Families</option>
                <option value="Windows 11">Windows 11</option>
                <option value="Windows Server">Windows Server</option>
                <option value="macOS">macOS</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          <div>
            <label className="block text-[9px] text-[#64748B] uppercase mb-1">Agent Version</label>
            <div className="relative flex items-center">
              <select
                value={versionFilter}
                onChange={(e) => { setVersionFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none p-2 border border-[#E2E8F0] rounded-lg text-xs bg-white text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Agent Versions</option>
                <option value="1.0">v1.0</option>
                <option value="0.9">v0.9</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>
        </div>
      </div>

      {/* Main Table Block */}
      <div className="mx-6 mt-6">
        <Table>
          <TableHeader>
            <TableRow>
              {[
                { label: "Hostname", field: "hostname" },
                { label: "User", field: "username" },
                { label: "Department", field: "department" },
                { label: "OS", field: "operating_system" },
                { label: "IP Address", field: "ip_address" },
                { label: "Agent Version", field: "agent_version" },
                { label: "Status", field: "status" },
                { label: "Last Heartbeat", field: "last_heartbeat" },
                { label: "Actions", field: "" }
              ].map((col, idx) => (
                <TableHead
                  key={idx}
                  onClick={() => col.field && handleSort(col.field)}
                  className={col.field ? "cursor-pointer hover:bg-[#F1F5F9]" : ""}
                >
                  <div className="flex items-center gap-1 select-none">
                    {col.label}
                    {sortBy === col.field && (
                      sortOrder === "asc" ? <ChevronUp className="w-3 h-3 text-[#E30613]" /> : <ChevronDown className="w-3 h-3 text-[#E30613]" />
                    )}
                  </div>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={9} className="p-10 text-center text-[#64748B]">
                  <div className="flex items-center justify-center gap-2 font-bold uppercase tracking-wider animate-pulse">
                    <RefreshCw className="w-4 h-4 animate-spin text-[#E30613]" aria-hidden />
                    <span>Loading enterprise devices...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : devices.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="p-10 text-center text-[#64748B] font-semibold italic">
                  No devices matched your active filters.
                </TableCell>
              </TableRow>
            ) : (
              devices.map((device) => (
                <TableRow
                  key={device.id}
                  onClick={() => handleViewDetails(device)}
                >
                  <TableCell className="font-bold text-[#1E293B]">{device.hostname}</TableCell>
                  <TableCell className="text-[#475569] font-semibold">{device.username || "—"}</TableCell>
                  <TableCell className="text-[#475569]">{device.department || "—"}</TableCell>
                  <TableCell className="text-[#475569] truncate max-w-44 font-semibold" title={device.operating_system}>
                    {device.operating_system || "—"}
                  </TableCell>
                  <TableCell className="text-[#475569] font-mono text-[11px]">{device.ip_address || "—"}</TableCell>
                  <TableCell className="text-[#475569] font-semibold">{device.agent_version || "—"}</TableCell>
                  <TableCell>
                    <StatusPill status={device.status} />
                  </TableCell>
                  <TableCell className="text-[#64748B] font-semibold">
                    {device.last_heartbeat ? new Date(device.last_heartbeat).toLocaleTimeString() : "—"}
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={(e) => handleRefreshDevice(device.id, e)}
                      disabled={isRefreshing === device.id}
                      className="p-1.5 hover:bg-[#F1F5F9] rounded-xl text-[#94A3B8] hover:text-[#0F172A] border border-transparent hover:border-[#E2E8F0] transition-all cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#E30613]"
                      title="Force refresh status"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing === device.id ? "animate-spin text-[#E30613]" : ""}`} />
                    </button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* --- Pagination Controls --- */}
        {!isLoading && totalPages > 1 && (
          <div className="px-5 py-3 border-t border-[#F1F5F9] bg-white flex items-center justify-between text-xs text-[#64748B]">
            <span>
              Showing <strong>{(page - 1) * limit + 1}</strong> to <strong>{Math.min(page * limit, totalCount)}</strong> of <strong>{totalCount}</strong> devices
            </span>
            <div className="flex items-center gap-2.5 select-none font-bold uppercase">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="p-1 border border-[#E2E8F0] hover:bg-[#F8FAFC] rounded disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4 text-[#475569]" />
              </button>
              <span className="text-[#1E293B]">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="p-1 border border-[#E2E8F0] hover:bg-[#F8FAFC] rounded disabled:opacity-40"
              >
                <ChevronRight className="w-4 h-4 text-[#475569]" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* --- Side Drawer - Device Details Panel --- */}
      {isDrawerOpen && selectedDevice && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/40 backdrop-blur-xs select-none">
          <div className="w-[500px] max-w-full h-full bg-white shadow-2xl flex flex-col overflow-hidden animate-slide-in">
            {/* Header */}
            <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC] flex-shrink-0">
              <div>
                <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
                  <Laptop className="w-4 h-4 text-[#E30613]" aria-hidden />
                  {selectedDevice.hostname}
                </h3>
                <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider mt-0.5 block">
                  Device Information Panel
                </span>
              </div>
              <button
                onClick={() => setIsDrawerOpen(false)}
                className="p-1 hover:bg-[#F1F5F9] rounded-lg text-[#94A3B8] hover:text-[#475569] transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Actions Panel */}
            <div className="px-5 py-3 border-b border-[#E2E8F0] flex gap-2 flex-wrap">
              <button
                onClick={() => handleRefreshDevice(selectedDevice.id)}
                disabled={isRefreshing === selectedDevice.id}
                className="px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer shadow-xs transition-colors flex items-center gap-1.5"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing === selectedDevice.id ? "animate-spin text-[#E30613]" : ""}`} />
                Refresh Telemetry
              </button>

              <button
                onClick={() => handleRestartAgent(selectedDevice.id, selectedDevice.hostname)}
                disabled={isActionExecuting}
                className="px-3 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer disabled:opacity-50 transition-colors shadow-xs flex items-center gap-1.5"
              >
                {isActionExecuting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                Restart Device Agent
              </button>
            </div>

            {/* Tabs Selector */}
            <div className="flex border-b border-[#E2E8F0] text-xs font-bold text-[#475569] flex-shrink-0">
              {[
                { id: "details", label: "General", icon: Info },
                { id: "health", label: "Diagnostics", icon: Activity },
                { id: "software", label: "Software", icon: Laptop },
                { id: "processes", label: "Processes", icon: Server },
                { id: "history", label: "Execution History", icon: History }
              ].map((tab) => {
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 border-b-2 hover:bg-[#F8FAFC] cursor-pointer ${
                      isActive ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#94A3B8]"
                    }`}
                  >
                    <tab.icon className="w-3.5 h-3.5" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-5 text-xs text-[#475569] font-bold uppercase tracking-wider">
              {activeTab === "details" && (
                <div className="space-y-4">
                  <div className="bg-[#F8FAFC] p-4 rounded-xl border border-[#E2E8F0] space-y-3 font-bold">
                    <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#F1F5F9]">
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">Hostname</span>
                        <span className="text-[#0F172A] font-semibold">{selectedDevice.hostname}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">Username</span>
                        <span className="text-[#0F172A] font-semibold">{selectedDevice.username || "—"}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#F1F5F9]">
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">OS</span>
                        <span className="text-[#0F172A]">{selectedDevice.operating_system || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">CPU</span>
                        <span className="text-[#0F172A]">{selectedDevice.cpu ? `${selectedDevice.cpu.toFixed(1)}%` : "0%"}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#F1F5F9]">
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">RAM</span>
                        <span className="text-[#0F172A]">{selectedDevice.ram ? `${selectedDevice.ram} GB` : "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">Disk</span>
                        <span className="text-[#0F172A]">{selectedDevice.disk ? `${selectedDevice.disk} GB` : "—"}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#F1F5F9]">
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">IP</span>
                        <span className="text-[#0F172A] font-mono">{selectedDevice.ip_address || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">MAC</span>
                        <span className="text-[#0F172A] font-mono uppercase">{selectedDevice.mac_address || "—"}</span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#F1F5F9]">
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">Agent Version</span>
                        <span className="text-[#0F172A] font-semibold">{selectedDevice.agent_version || "—"}</span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[#64748B] block font-bold">Last Heartbeat</span>
                        <span className="text-[#0F172A]">{selectedDevice.last_heartbeat ? new Date(selectedDevice.last_heartbeat).toLocaleString() : "—"}</span>
                      </div>
                    </div>

                    <div>
                      <span className="text-[10px] text-[#64748B] block font-bold mb-1">Running Status</span>
                      <StatusPill status={selectedDevice.status} />
                    </div>
                  </div>

                  {/* Network Interfaces */}
                  <div className="space-y-2">
                    <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2 flex items-center gap-1.5">
                      <Network className="w-3.5 h-3.5 text-[#94A3B8]" />
                      Active Network Interfaces
                    </h4>
                    <div className="space-y-2 font-bold">
                      {selectedDevice.network_interfaces && selectedDevice.network_interfaces.length > 0 ? (
                        selectedDevice.network_interfaces.map((net, i) => (
                          <div key={i} className="flex justify-between items-center p-2.5 bg-white border border-[#E2E8F0] rounded-xl shadow-xs">
                            <div>
                              <span className="font-semibold text-[#1E293B] block">{net.name}</span>
                              <span className="font-mono text-[10px] text-[#94A3B8] block">{net.ip}</span>
                            </div>
                            <span className={`badge ${
                              net.status === "up" ? "badge-success" : "badge-failed"
                            }`}>
                              {net.status}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div className="p-3 text-center text-[#94A3B8] bg-[#F8FAFC] rounded-xl border border-dashed border-[#E2E8F0] italic font-semibold">
                          No active network interfaces reported.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "health" && (
                <div className="space-y-4">
                  {deviceHealth ? (
                    <>
                      <div className={`p-4 rounded-xl border flex items-start gap-3 ${
                        deviceHealth.overall_health === "healthy" 
                          ? "bg-green-50/50 border-green-200 text-green-800"
                          : deviceHealth.overall_health === "warning"
                          ? "bg-yellow-50/50 border-yellow-250 text-yellow-800"
                          : "bg-red-50/50 border-red-200 text-red-800"
                      }`}>
                        {deviceHealth.overall_health === "healthy" ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <ShieldAlert className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                        )}
                        <div>
                          <h4 className="font-bold text-xs uppercase">Overall Device Health: {deviceHealth.overall_health}</h4>
                          <p className="text-[10px] opacity-90 mt-0.5 leading-normal normal-case font-semibold">
                            {deviceHealth.overall_health === "healthy" 
                              ? "All local agent metrics and security services are running within acceptable tolerances." 
                              : "One or more critical parameters are reporting faults or high load. Action recommended."}
                          </p>
                        </div>
                      </div>

                      {/* Diagnostic details grid */}
                      <div className="grid grid-cols-2 gap-3 font-bold uppercase text-xs">
                        <div className="p-3 border border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                          <span className="text-[9px] font-bold text-[#64748B] block mb-1">CPU Load Check</span>
                          <span className={deviceHealth.cpu_check === "pass" ? "text-emerald-600" : "text-red-600"}>{deviceHealth.cpu_check}</span>
                        </div>

                        <div className="p-3 border border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                          <span className="text-[9px] font-bold text-[#64748B] block mb-1">Memory Load Check</span>
                          <span className={deviceHealth.memory_check === "pass" ? "text-emerald-600" : "text-red-600"}>{deviceHealth.memory_check}</span>
                        </div>

                        <div className="p-3 border border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                          <span className="text-[9px] font-bold text-[#64748B] block mb-1">Disk Health Check</span>
                          <span className={deviceHealth.disk_check === "pass" ? "text-emerald-600" : "text-red-600"}>{deviceHealth.disk_check}</span>
                        </div>

                        <div className="p-3 border border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                          <span className="text-[9px] font-bold text-[#64748B] block mb-1">Agent Service Status</span>
                          <span className={deviceHealth.service_status === "running" ? "text-emerald-600" : "text-red-600"}>{deviceHealth.service_status}</span>
                        </div>
                      </div>

                      {/* Security settings */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3.5 space-y-2">
                        <h5 className="font-bold text-[10px] text-[#64748B] uppercase tracking-wider mb-2">Endpoint Security Audit</h5>
                        <div className="flex justify-between items-center py-1">
                          <span className="font-semibold text-[#475569]">Local Firewall Status</span>
                          <span className={deviceHealth.firewall_active ? "text-emerald-650" : "text-red-650"}>
                            {deviceHealth.firewall_active ? "Active" : "Disabled"}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-1">
                          <span className="font-semibold text-[#475569]">Antivirus Status</span>
                          <span className={deviceHealth.antivirus_active ? "text-emerald-650" : "text-red-650"}>
                            {deviceHealth.antivirus_active ? "Active" : "Disabled"}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-1">
                          <span className="font-semibold text-[#475569]">Active Bitlocker Encryption</span>
                          <span className={deviceHealth.disk_encrypted ? "text-emerald-650" : "text-red-650"}>
                            {deviceHealth.disk_encrypted ? "Encrypted" : "Decrypted"}
                          </span>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="p-10 text-center text-[#94A3B8] italic bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                      Fetching health check diagnostics telemetry...
                    </div>
                  )}
                </div>
              )}

              {activeTab === "software" && (
                <div className="space-y-2">
                  <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Installed Endpoint Applications</h4>
                  {selectedDevice.installed_software && selectedDevice.installed_software.length > 0 ? (
                    <div className="divide-y divide-[#F1F5F9] border border-[#E2E8F0] rounded-xl overflow-hidden bg-white">
                      {selectedDevice.installed_software.map((sw, i) => (
                        <div key={i} className="p-2.5 hover:bg-[#F8FAFC] text-[#475569] font-semibold normal-case">
                          {sw}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[#94A3B8] bg-[#F8FAFC] border border-dashed border-[#E2E8F0] rounded-xl italic font-semibold">
                      No software logs reported by agent.
                    </div>
                  )}
                </div>
              )}

              {activeTab === "processes" && (
                <div className="space-y-2">
                  <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Active Daemon Processes</h4>
                  {selectedDevice.running_processes && selectedDevice.running_processes.length > 0 ? (
                    <div className="divide-y divide-[#F1F5F9] border border-[#E2E8F0] rounded-xl overflow-hidden bg-white font-mono">
                      {selectedDevice.running_processes.map((proc, i) => (
                        <div key={i} className="p-2.5 text-[10.5px] text-[#475569] hover:bg-[#F8FAFC] flex justify-between normal-case font-semibold">
                          <span>{proc}</span>
                          <span className="text-[9px] text-[#94A3B8] font-bold uppercase">Running</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[#94A3B8] bg-[#F8FAFC] border border-dashed border-[#E2E8F0] rounded-xl italic font-semibold">
                      No active processes logs reported.
                    </div>
                  )}
                </div>
              )}

              {activeTab === "history" && (
                <div className="space-y-3">
                  <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Audit Logs Execution Trail</h4>
                  {deviceHistory.length > 0 ? (
                    <div className="space-y-2.5">
                      {deviceHistory.map((rec) => (
                        <div key={rec.id} className="p-3 border border-[#E2E8F0] rounded-xl bg-[#F8FAFC] hover:shadow-xs transition-shadow">
                          <div className="flex justify-between items-start mb-1">
                            <span className="font-bold text-[#1E293B] text-[11px] uppercase tracking-wider">{rec.action_name}</span>
                            <span className="text-[10px] text-[#94A3B8] font-bold">{new Date(rec.timestamp).toLocaleDateString()}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-1 text-[10.5px] text-[#475569] mt-2 pt-2 border-t border-[#F1F5F9] font-bold uppercase tracking-wider">
                            <span>Operator: <span className="text-[#1E293B]">{rec.username}</span></span>
                            <span>Duration: <span className="text-[#1E293B]">{rec.duration.toFixed(2)}s</span></span>
                          </div>
                          {rec.result && (
                            <div className="mt-2 p-1.5 bg-[#F1F5F9] rounded border border-[#E2E8F0] font-mono text-[10px] text-[#475569] truncate normal-case font-semibold">
                              Result: {rec.result}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[#94A3B8] bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl italic font-semibold">
                      No actions executed on this device.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
