"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch, NetworkError } from "@/lib/apiClient";
import { 
  Activity, Play, CheckCircle2, XCircle, Clock, Calendar, 
  ChevronDown, RefreshCw, X, ArrowUpRight, 
  Terminal, ShieldCheck, Cpu, HardDrive, User, Network
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

interface Execution {
  id: number;
  timestamp: string;
  username: string;
  device_id: string;
  department: string;
  action_name: string;
  status: string;
  result: string;
  duration: number;
  agent_version: string;
  parameters: any;
  started_at: string | null;
  completed_at: string | null;
  logs: string | null;
}

interface Stats {
  total_executions: number;
  success_rate: number;
  failure_rate: number;
  average_duration: number;
  most_used_action: string;
  least_used_action: string;
  successful_actions: number;
  failed_actions: number;
  running_actions: number;
  cancelled_actions: number;
  pending_actions: number;
  todays_executions: number;
}

interface ExecutionCenterProps {
  user: any;
  token: string | null;
  apiBaseUrl: string;
}

export default function ExecutionCenter({ user, token, apiBaseUrl }: ExecutionCenterProps) {
  // --- States ---
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [stats, setStats] = useState<Stats>({
    total_executions: 0,
    success_rate: 0,
    failure_rate: 0,
    average_duration: 0,
    most_used_action: "None",
    least_used_action: "None",
    successful_actions: 0,
    failed_actions: 0,
    running_actions: 0,
    cancelled_actions: 0,
    pending_actions: 0,
    todays_executions: 0
  });

  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [empFilter, setEmpFilter] = useState("");
  const [hostFilter, setHostFilter] = useState("");
  const [deptFilter, setDeptFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortBy, setSortBy] = useState("timestamp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const [selectedExec, setSelectedExec] = useState<Execution | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // --- Auth Headers Helper ---
  const getAuthHeaders = () => ({
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  });

  // --- Fetch Data ---
  const fetchData = async (silent = false) => {
    if (!silent) setIsLoading(true);
    try {
      // 1. Fetch statistics
      const statsRes = await apiFetch(`${apiBaseUrl}/api/executions/statistics`, {
        headers: getAuthHeaders()
      });
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      // 2. Fetch list
      const queryParams = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_order: sortOrder
      });

      if (search) queryParams.append("search", search);
      if (statusFilter) queryParams.append("status_filter", statusFilter);
      if (empFilter) queryParams.append("employee", empFilter);
      if (hostFilter) queryParams.append("hostname", hostFilter);
      if (deptFilter) queryParams.append("department", deptFilter);
      if (actionFilter) queryParams.append("action", actionFilter);
      if (startDate) queryParams.append("start_date", startDate);
      if (endDate) queryParams.append("end_date", endDate);

      const listRes = await apiFetch(`${apiBaseUrl}/api/executions?${queryParams.toString()}`, {
        headers: getAuthHeaders()
      });
      if (listRes.ok) {
        const listData = await listRes.json();
        setExecutions(listData.executions);
        setTotalCount(listData.total);
      }
    } catch (error) {
      if (!(error instanceof NetworkError)) {
        // Only log unexpected HTTP-layer errors, not connection failures
        console.warn("Execution fetch failed (non-network):", error);
      }
      // NetworkError: silently skip, backend may be temporarily offline
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  // Trigger fetch on query change
  useEffect(() => {
    fetchData();
  }, [page, sortBy, sortOrder, search, statusFilter, empFilter, hostFilter, deptFilter, actionFilter, startDate, endDate]);

  // Realtime Polling loop (every 10s)
  useEffect(() => {
    const timer = setInterval(() => {
      fetchData(true);
    }, 10000);
    return () => clearInterval(timer);
  }, [page, sortBy, sortOrder, search, statusFilter, empFilter, hostFilter, deptFilter, actionFilter, startDate, endDate]);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    fetchData(true);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearchInput("");
    setSearch("");
    setStatusFilter("");
    setEmpFilter("");
    setHostFilter("");
    setDeptFilter("");
    setActionFilter("");
    setStartDate("");
    setEndDate("");
    setPage(1);
  };

  const handleRowClick = (exec: Execution) => {
    setSelectedExec(exec);
    setIsDrawerOpen(true);
  };

  // Collect unique filter options from current page (or seed values)
  const uniqueEmployees = Array.from(new Set(executions.map(e => e.username)));
  const uniqueHosts = Array.from(new Set(executions.map(e => e.device_id)));
  const uniqueDepts = Array.from(new Set(executions.map(e => e.department)));

  const totalPages = Math.ceil(totalCount / limit);

  return (
    <div className="flex-1 bg-[#F8FAFC] min-h-screen text-[#1E293B] flex flex-col font-sans">
      
      {/* Header bar */}
      <div className="px-6 py-4 bg-white border-b border-[#E2E8F0] flex justify-between items-center shadow-xs">
        <div>
          <h1 className="text-[16px] font-bold text-[#0F172A] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#E30613]" aria-hidden />
            Enterprise Execution Center
          </h1>
          <p className="text-xs text-[#64748B] mt-0.5">
            Centralized action registry, permission auditing, and real-time execution statistics.
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer shadow-xs transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#E30613]" : ""}`} aria-hidden />
          {isRefreshing ? "Syncing..." : "Refresh"}
        </button>
      </div>

      {/* STATISTICS CARDS */}
      <div className="p-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[
          { label: "Total Executions", count: stats.total_executions, icon: Activity, color: "text-[#E30613] bg-red-50 border-red-100" },
          { label: "Successful Actions", count: stats.successful_actions, icon: CheckCircle2, color: "text-[#16A34A] bg-[#F0FDF4] border-[#BBF7D0]" },
          { label: "Failed Actions", count: stats.failed_actions, icon: XCircle, color: "text-[#DC2626] bg-[#FEF2F2] border-[#FECACA]" },
          { label: "Running Actions", count: stats.running_actions, icon: RefreshCw, color: "text-[#2563EB] bg-[#EFF6FF] border-[#BFDBFE]" },
          { label: "Avg Duration", count: `${stats.average_duration.toFixed(2)}s`, icon: Clock, color: "text-purple-700 bg-purple-50 border-purple-100" },
          { label: "Today's Executions", count: stats.todays_executions, icon: Calendar, color: "text-emerald-750 bg-emerald-50 border-emerald-100" }
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

      {/* FILTERS & SEARCH CONTROL PANEL */}
      <div className="mx-6 p-4 bg-white border border-[#E2E8F0] rounded-xl shadow-xs space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
          <div className="flex-1">
            <SearchInput
              placeholder="Search by Execution ID, employee name, or device..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="px-3.5 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer shadow-xs transition-colors"
            >
              Search
            </button>
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl cursor-pointer shadow-xs transition-colors"
            >
              Reset Filters
            </button>
          </div>
        </form>

        {/* Dropdown Filters Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 font-bold">
          {/* Status */}
          <div className="flex flex-col gap-1">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">Status</span>
            <div className="relative flex items-center">
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none bg-white border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Statuses</option>
                <option value="Success">Success</option>
                <option value="Failed">Failed</option>
                <option value="Running">Running</option>
                <option value="Pending">Pending</option>
                <option value="Cancelled">Cancelled</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          {/* Employee */}
          <div className="flex flex-col gap-1">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">Employee</span>
            <div className="relative flex items-center">
              <select
                value={empFilter}
                onChange={(e) => { setEmpFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none bg-white border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Employees</option>
                {uniqueEmployees.map((emp, i) => (
                  <option key={i} value={emp}>{emp}</option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          {/* Hostname */}
          <div className="flex flex-col gap-1">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">Device Host</span>
            <div className="relative flex items-center">
              <select
                value={hostFilter}
                onChange={(e) => { setHostFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none bg-white border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Devices</option>
                {uniqueHosts.map((host, i) => (
                  <option key={i} value={host}>{host}</option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          {/* Department */}
          <div className="flex flex-col gap-1">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">Department</span>
            <div className="relative flex items-center">
              <select
                value={deptFilter}
                onChange={(e) => { setDeptFilter(e.target.value); setPage(1); }}
                className="w-full appearance-none bg-white border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#475569] focus:outline-none focus:border-[#E30613]"
              >
                <option value="">All Departments</option>
                {uniqueDepts.map((dept, i) => (
                  <option key={i} value={dept}>{dept}</option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-[#94A3B8] absolute right-2.5 pointer-events-none" aria-hidden />
            </div>
          </div>

          {/* Date Range Start */}
          <div className="flex flex-col gap-1 text-[#475569]">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">Start Date</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
              className="w-full bg-white border border-[#E2E8F0] rounded-lg px-3 py-1 text-xs focus:outline-none focus:border-[#E30613]"
            />
          </div>

          {/* Date Range End */}
          <div className="flex flex-col gap-1 text-[#475569]">
            <span className="text-[9px] font-bold text-[#64748B] uppercase">End Date</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
              className="w-full bg-white border border-[#E2E8F0] rounded-lg px-3 py-1 text-xs focus:outline-none focus:border-[#E30613]"
            />
          </div>
        </div>
      </div>

      {/* TABLE LAYOUT */}
      <div className="mx-6 mt-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Execution ID</TableHead>
              <TableHead className="cursor-pointer select-none hover:text-[#0F172A]" onClick={() => {
                setSortBy("timestamp");
                setSortOrder(sortOrder === "asc" ? "desc" : "asc");
              }}>
                Timestamp {sortBy === "timestamp" && (sortOrder === "asc" ? "▲" : "▼")}
              </TableHead>
              <TableHead>Employee</TableHead>
              <TableHead>Device</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Action</TableHead>
              <TableHead className="cursor-pointer select-none hover:text-[#0F172A]" onClick={() => {
                setSortBy("status");
                setSortOrder(sortOrder === "asc" ? "desc" : "asc");
              }}>
                Status {sortBy === "status" && (sortOrder === "asc" ? "▲" : "▼")}
              </TableHead>
              <TableHead className="cursor-pointer select-none hover:text-[#0F172A]" onClick={() => {
                setSortBy("duration");
                setSortOrder(sortOrder === "asc" ? "desc" : "asc");
              }}>
                Duration {sortBy === "duration" && (sortOrder === "asc" ? "▲" : "▼")}
              </TableHead>
              <TableHead>Agent Version</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-10 text-[#64748B] font-bold uppercase tracking-wider animate-pulse">
                  <RefreshCw className="w-5 h-5 text-[#94A3B8] animate-spin mx-auto mb-2" aria-hidden />
                  Querying centralized action logs...
                </TableCell>
              </TableRow>
            ) : executions.length > 0 ? (
              executions.map((e) => (
                <TableRow 
                  key={e.id}
                  onClick={() => handleRowClick(e)}
                >
                  <TableCell className="font-mono font-bold text-[#64748B]">#{e.id}</TableCell>
                  <TableCell className="text-[#475569] font-semibold">{new Date(e.timestamp).toLocaleString()}</TableCell>
                  <TableCell className="font-bold text-[#1E293B]">
                    <span className="flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-[#94A3B8]" aria-hidden />
                      {e.username}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-[#475569]">{e.device_id}</TableCell>
                  <TableCell className="font-semibold text-[#475569]">{e.department}</TableCell>
                  <TableCell className="font-bold text-[#1E293B]">{e.action_name}</TableCell>
                  <TableCell>
                    <StatusPill status={e.status} />
                  </TableCell>
                  <TableCell className="font-mono text-[#475569]">{e.duration.toFixed(2)}s</TableCell>
                  <TableCell className="text-[#475569] font-bold">{e.agent_version}</TableCell>
                  <TableCell className="text-right">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRowClick(e);
                      }}
                      className="px-2.5 py-1 text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl font-bold text-[10.5px] cursor-pointer border border-[#E2E8F0] shadow-xs"
                    >
                      Inspect
                    </button>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-12 text-[#64748B] italic font-semibold uppercase">
                  No matching executions found. Modify filters or trigger actions.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="px-6 py-4 bg-white border-t border-[#E2E8F0] rounded-b-xl flex justify-between items-center text-xs select-none">
            <span className="text-[#64748B] font-semibold">
              Showing page {page} of {totalPages} ({totalCount} total entries)
            </span>
            <div className="flex gap-1">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
                className="px-3 py-1.5 bg-white border border-[#CBD5E1] rounded hover:border-[#94A3B8] hover:bg-[#F8FAFC] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
              >
                Previous
              </button>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                className="px-3 py-1.5 bg-white border border-[#CBD5E1] rounded hover:border-[#94A3B8] hover:bg-[#F8FAFC] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* --- SIDE DETAILS DRAWER --- */}
      {isDrawerOpen && selectedExec && (
        <div className="fixed inset-y-0 right-0 w-120 bg-white border-l border-[#E2E8F0] shadow-2xl flex flex-col z-50 animate-slide-in">
          {/* Drawer Header */}
          <div className="p-5 border-b border-[#E2E8F0] flex justify-between items-center">
            <div>
              <span className="text-[9px] font-black text-[#E30613] uppercase tracking-wider">Execution Registry Details</span>
              <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-1.5 mt-0.5">
                <Terminal className="w-4.5 h-4.5 text-[#64748B]" aria-hidden />
                Execution #{selectedExec.id}
              </h3>
            </div>
            <button 
              onClick={() => setIsDrawerOpen(false)}
              className="p-1.5 hover:bg-[#F1F5F9] rounded-lg text-[#94A3B8] hover:text-[#475569] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-5 text-xs text-[#475569] space-y-5 font-bold uppercase tracking-wider">
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-[#E2E8F0] space-y-3 font-bold">
              <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#E2E8F0]">
                <div>
                  <span className="text-[10px] text-[#64748B] block">Action Name</span>
                  <span className="text-[#0F172A] font-bold text-[13px]">{selectedExec.action_name}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748B] block">Status Badge</span>
                  <StatusPill status={selectedExec.status} className="mt-1" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#E2E8F0]">
                <div>
                  <span className="text-[10px] text-[#64748B] block">Employee</span>
                  <span className="text-[#0F172A] font-semibold">{selectedExec.username}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748B] block">Department</span>
                  <span className="text-[#0F172A] font-semibold">{selectedExec.department}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pb-2.5 border-b border-[#E2E8F0]">
                <div>
                  <span className="text-[10px] text-[#64748B] block">Target Device Host</span>
                  <span className="text-[#0F172A] font-mono">{selectedExec.device_id}</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748B] block">Agent Version</span>
                  <span className="text-[#0F172A] font-mono font-bold">{selectedExec.agent_version}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-[#64748B] block">Execution Duration</span>
                  <span className="text-[#0F172A] font-mono">{selectedExec.duration.toFixed(2)}s</span>
                </div>
                <div>
                  <span className="text-[10px] text-[#64748B] block">Raw Result</span>
                  <span className="text-[#0F172A] font-mono font-semibold">{selectedExec.result}</span>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div>
              <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Timestamp Logs</h4>
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-3 grid grid-cols-2 gap-2 font-bold uppercase">
                <div>
                  <span className="text-[9px] text-[#94A3B8] block">Started At</span>
                  <span className="font-semibold text-[#475569]">
                    {selectedExec.started_at ? new Date(selectedExec.started_at).toLocaleString() : "None"}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] text-[#94A3B8] block">Completed At</span>
                  <span className="font-semibold text-[#475569]">
                    {selectedExec.completed_at ? new Date(selectedExec.completed_at).toLocaleString() : "None"}
                  </span>
                </div>
              </div>
            </div>

            {/* Action Parameters */}
            <div>
              <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Parameters Payload</h4>
              <div className="bg-slate-950 rounded-xl p-3.5 border border-slate-900 overflow-x-auto normal-case">
                <pre className="font-mono text-[11px] text-green-400 leading-normal">
                  {JSON.stringify(selectedExec.parameters || {}, null, 2)}
                </pre>
              </div>
            </div>

            {/* Output Logs */}
            <div className="flex-1 flex flex-col min-h-40 normal-case font-semibold">
              <h4 className="font-bold text-[10px] uppercase text-[#64748B] tracking-wider mb-2">Terminal Logs Output</h4>
              <div className="bg-slate-950 rounded-xl p-3.5 border border-slate-900 font-mono text-[11px] text-slate-300 whitespace-pre-wrap overflow-y-auto leading-relaxed max-h-80 select-text">
                {selectedExec.logs || "[INFO] No output logs reported by Device Agent."}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
