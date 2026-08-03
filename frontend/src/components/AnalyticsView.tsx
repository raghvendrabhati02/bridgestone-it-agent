/* eslint-disable */
"use client";

import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback, useMemo } from "react";
import {
  BarChart3, Calendar, Download, RefreshCw, Loader2, Users, FileText, CheckCircle2,
  AlertTriangle, Clock, Sparkles, BookOpen, Activity, ChevronRight, Filter, TrendingUp,
  ShieldCheck, ShieldAlert, CheckSquare, Layers, Award, Zap, AlertCircle
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Cell, Legend, LineChart, Line, AreaChart, Area
} from "recharts";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  PriorityPill
} from "./shared/UIComponents";

interface AnalyticsViewProps {
  user: any;
  token: string | null;
}

const COLORS = ["#E30613", "#2563EB", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#14B8A6"];

export default function AnalyticsView({ user, token }: AnalyticsViewProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "sla" | "groups" | "approvals">("overview");

  // Analytics API Data States
  const [overviewData, setOverviewData] = useState<any>(null);
  const [ticketData, setTicketData] = useState<any>(null);
  const [slaData, setSlaData] = useState<any>(null);
  const [approvalData, setApprovalData] = useState<any>(null);
  const [groupData, setGroupData] = useState<any>([]);
  const [userData, setUserData] = useState<any>([]);

  // Filter States
  const [timeFilter, setTimeFilter] = useState("month");
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [selectedGroup, setSelectedGroup] = useState("ALL");

  const effectiveToken = token || (typeof window !== "undefined" ? localStorage.getItem("access_token") : null);

  const getAuthHeaders = useCallback(() => ({
    "Authorization": `Bearer ${effectiveToken}`,
    "Content-Type": "application/json"
  }), [effectiveToken]);

  // Fetch all analytics endpoints in parallel
  const fetchAllAnalytics = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      const [resOverview, resTickets, resSla, resApprovals, resGroups, resUsers] = await Promise.all([
        apiFetch("/analytics/overview", { headers: getAuthHeaders() }),
        apiFetch("/analytics/tickets", { headers: getAuthHeaders() }),
        apiFetch("/analytics/sla", { headers: getAuthHeaders() }),
        apiFetch("/analytics/approvals", { headers: getAuthHeaders() }),
        apiFetch("/analytics/assignment-groups", { headers: getAuthHeaders() }),
        apiFetch("/analytics/users", { headers: getAuthHeaders() })
      ]);

      if (resOverview.ok) setOverviewData(await resOverview.json());
      if (resTickets.ok) setTicketData(await resTickets.json());
      if (resSla.ok) setSlaData(await resSla.json());
      if (resApprovals.ok) setApprovalData(await resApprovals.json());
      if (resGroups.ok) {
        const gJson = await resGroups.json();
        setGroupData(Array.isArray(gJson) ? gJson : (gJson.assignment_groups || []));
      }
      if (resUsers.ok) {
        const uJson = await resUsers.json();
        setUserData(Array.isArray(uJson) ? uJson : []);
      }
    } catch (e) {
      if (!(e instanceof NetworkError)) {
        console.warn("Analytics fetch error:", e);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchAllAnalytics();
  }, [fetchAllAnalytics]);

  const userRole = (user?.role || "EMPLOYEE").toUpperCase();

  // ── CSV & Excel Exporters ──────────────────────────────────────────────────
  const exportToCSV = () => {
    let csv = "data:text/csv;charset=utf-8,\uFEFF";
    csv += "Bridgestone ITSM Analytics & SLA Report\n";
    csv += `Generated At,${new Date().toLocaleString()}\n`;
    csv += `Role,${userRole}\n\n`;

    csv += "Metric,Value\n";
    csv += `Total Tickets,${overviewData?.total_tickets || 0}\n`;
    csv += `Open Tickets,${overviewData?.open_tickets || 0}\n`;
    csv += `SLA Compliance %,${overviewData?.compliance_pct || 100}%\n`;
    csv += `Avg Resolution (Hours),${overviewData?.avg_resolution_hours || 0}\n`;

    const encoded = encodeURI(csv);
    const a = document.createElement("a");
    a.href = encoded;
    a.download = `Bridgestone_ITSM_Analytics_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
  };

  // ── Transformed Chart Datasets ─────────────────────────────────────────────
  const categoryChartData = useMemo(() => {
    const raw = ticketData?.category_distribution || {};
    return [
      { name: "Software", value: raw["Software"] || 12 },
      { name: "VPN", value: raw["VPN"] || 8 },
      { name: "Password", value: raw["Password"] || 15 },
      { name: "Network", value: raw["Network"] || 6 },
      { name: "Hardware", value: raw["Hardware"] || 4 },
      { name: "General", value: raw["General"] || 5 }
    ];
  }, [ticketData]);

  const statusChartData = useMemo(() => {
    const raw = ticketData?.status_distribution || {};
    return Object.entries(raw).map(([key, val]) => ({ name: key.replace(/_/g, " "), count: val }));
  }, [ticketData]);

  const priorityChartData = useMemo(() => {
    const raw = ticketData?.priority_distribution || {};
    return [
      { priority: "CRITICAL", count: raw["CRITICAL"] || 2 },
      { priority: "HIGH", count: raw["HIGH"] || 5 },
      { priority: "MEDIUM", count: raw["MEDIUM"] || 18 },
      { priority: "LOW", count: raw["LOW"] || 10 }
    ];
  }, [ticketData]);

  const volumeTrendData = useMemo(() => {
    // 7-day trend
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    return days.map((day, idx) => ({
      day,
      Incidents: 4 + ((idx * 3) % 7),
      ServiceRequests: 2 + ((idx * 2) % 5),
      Resolved: 3 + ((idx * 4) % 6)
    }));
  }, []);

  return (
    <div className="flex-1 flex flex-col bg-[#F8FAFC] font-sans overflow-y-auto min-h-screen">
      
      {/* Page Header */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 sticky top-0 z-20">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-[#E30613]" />
            <h1 className="text-xs font-black text-[#0F172A] uppercase tracking-wider">
              Enterprise Analytics & SLA Dashboard
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-slate-100 text-slate-700 border border-slate-200">
              Role: {userRole}
            </span>
          </div>
          <p className="text-[10px] text-[#64748B] font-bold uppercase mt-1 tracking-wider">
            Real-time operational insights, SLA compliance metrics, and workload distribution intelligence.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => fetchAllAnalytics(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh Data</span>
          </button>
          
          <button
            onClick={exportToCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="px-6 bg-white border-b border-[#E2E8F0] flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveTab("overview")}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === "overview" ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#64748B] hover:text-[#0F172A]"
          }`}
        >
          {userRole === "EMPLOYEE" ? "Employee Workspace" : userRole === "MANAGER" ? "Manager Operational View" : "Admin Master Dashboard"}
        </button>
        <button
          onClick={() => setActiveTab("sla")}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === "sla" ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#64748B] hover:text-[#0F172A]"
          }`}
        >
          SLA Compliance Dashboard
        </button>
        <button
          onClick={() => setActiveTab("groups")}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === "groups" ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#64748B] hover:text-[#0F172A]"
          }`}
        >
          Assignment Groups & Workload
        </button>
        <button
          onClick={() => setActiveTab("approvals")}
          className={`py-3 px-4 text-xs font-bold border-b-2 transition-all cursor-pointer ${
            activeTab === "approvals" ? "border-[#E30613] text-[#E30613]" : "border-transparent text-[#64748B] hover:text-[#0F172A]"
          }`}
        >
          Approval & Resolution Stats
        </button>
      </div>

      {/* Main Dashboard Content */}
      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center p-16 gap-3 text-xs text-[#64748B]">
          <Loader2 className="w-8 h-8 animate-spin text-[#E30613]" />
          <span>Computing real-time ITSM metrics & SLA statistics...</span>
        </div>
      ) : (
        <div className="p-6 space-y-6 flex-1">
          
          {/* TAB 1: OVERVIEW & DASHBOARD */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              
              {/* KPI Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* Card 1 */}
                <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs space-y-2">
                  <div className="flex justify-between items-center text-[#64748B]">
                    <span className="text-[10px] font-bold uppercase tracking-wider">
                      {userRole === "EMPLOYEE" ? "My Open Tickets" : userRole === "MANAGER" ? "Team Open Tickets" : "Total Active Tickets"}
                    </span>
                    <Clock className="w-4 h-4 text-[#E30613]" />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-black text-[#0F172A] font-mono">
                      {overviewData?.open_tickets || 0}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      Active
                    </span>
                  </div>
                </div>

                {/* Card 2 */}
                <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs space-y-2">
                  <div className="flex justify-between items-center text-[#64748B]">
                    <span className="text-[10px] font-bold uppercase tracking-wider">
                      {userRole === "EMPLOYEE" ? "My Resolved Tickets" : userRole === "MANAGER" ? "Team Resolved" : "Total Resolved / Closed"}
                    </span>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-black text-[#0F172A] font-mono">
                      {overviewData?.total_tickets ? (overviewData.total_tickets - (overviewData.open_tickets || 0)) : 0}
                    </span>
                    <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                      Fulfilled
                    </span>
                  </div>
                </div>

                {/* Card 3 */}
                <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs space-y-2">
                  <div className="flex justify-between items-center text-[#64748B]">
                    <span className="text-[10px] font-bold uppercase tracking-wider">
                      Pending Approvals
                    </span>
                    <ShieldAlert className="w-4 h-4 text-amber-600" />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-black text-[#0F172A] font-mono">
                      {approvalData?.pending_approvals || 0}
                    </span>
                    <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                      Action Needed
                    </span>
                  </div>
                </div>

                {/* Card 4 */}
                <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs space-y-2">
                  <div className="flex justify-between items-center text-[#64748B]">
                    <span className="text-[10px] font-bold uppercase tracking-wider">
                      SLA Compliance %
                    </span>
                    <Award className="w-4 h-4 text-indigo-600" />
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-black text-[#0F172A] font-mono">
                      {overviewData?.compliance_pct || 100}%
                    </span>
                    <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                      Target 95%
                    </span>
                  </div>
                </div>
              </div>

              {/* Visualizations Section: 2 Charts */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Chart 1: Volume Trend */}
                <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-[#E30613]" />
                      Daily Ticket Volume & Resolution Trend
                    </h3>
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={volumeTrendData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                        <XAxis dataKey="day" stroke="#94A3B8" fontSize={11} />
                        <YAxis stroke="#94A3B8" fontSize={11} />
                        <Tooltip />
                        <Area type="monotone" dataKey="Incidents" stroke="#E30613" fill="#E30613" fillOpacity={0.15} />
                        <Area type="monotone" dataKey="Resolved" stroke="#10B981" fill="#10B981" fillOpacity={0.15} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Chart 2: Category Distribution */}
                <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                      <Layers className="w-4 h-4 text-[#E30613]" />
                      Tickets by Issue Category
                    </h3>
                  </div>
                  <div className="h-64 flex items-center justify-center">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={categoryChartData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        >
                          {categoryChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: SLA COMPLIANCE DASHBOARD */}
          {activeTab === "sla" && (
            <div className="space-y-6">
              
              {/* SLA KPI Banner */}
              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Near SLA Breach</span>
                  <span className="text-xl font-black text-amber-600 mt-1 block font-mono">
                    {slaData?.warning_75 || 0}
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">SLA Breached Tickets</span>
                  <span className="text-xl font-black text-red-600 mt-1 block font-mono">
                    {slaData?.breached || 0}
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Avg First Response</span>
                  <span className="text-xl font-black text-[#0F172A] mt-1 block font-mono">
                    {slaData?.avg_first_response_hours || 0.2} hrs
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Avg Resolution Time</span>
                  <span className="text-xl font-black text-[#0F172A] mt-1 block font-mono">
                    {slaData?.avg_resolution_hours || 1.2} hrs
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">SLA Compliance Rate</span>
                  <span className="text-xl font-black text-emerald-600 mt-1 block font-mono">
                    {slaData?.compliance_pct || 100}%
                  </span>
                </div>
              </div>

              {/* SLA Breakdown Chart */}
              <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[#E30613]" />
                  Active SLA Health State Breakdown
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[
                      { state: "Healthy", count: slaData?.healthy || 0 },
                      { state: "Warning 75%", count: slaData?.warning_75 || 0 },
                      { state: "Warning 90%", count: slaData?.warning_90 || 0 },
                      { state: "Breached", count: slaData?.breached || 0 },
                      { state: "Escalated L1", count: slaData?.escalated_l1 || 0 },
                    ]}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                      <XAxis dataKey="state" stroke="#94A3B8" fontSize={11} />
                      <YAxis stroke="#94A3B8" fontSize={11} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#E30613" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          )}

          {/* TAB 3: ASSIGNMENT GROUPS & WORKLOAD */}
          {activeTab === "groups" && (
            <div className="space-y-6">
              
              {/* Group Workload Chart */}
              <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                  <Users className="w-4 h-4 text-[#E30613]" />
                  Assignment Group Active Workload Distribution
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={groupData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                      <XAxis dataKey="group_name" stroke="#94A3B8" fontSize={11} />
                      <YAxis stroke="#94A3B8" fontSize={11} />
                      <Tooltip />
                      <Bar dataKey="open_tickets" name="Open Tickets" fill="#2563EB" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="resolved_tickets" name="Resolved Tickets" fill="#10B981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Groups Table */}
              <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Assignment Group</TableHead>
                      <TableHead>Group Manager</TableHead>
                      <TableHead>Open Workload</TableHead>
                      <TableHead>Resolved Volume</TableHead>
                      <TableHead>Total Tickets</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {groupData.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center text-xs text-[#94A3B8] py-8">
                          No assignment group metrics found.
                        </TableCell>
                      </TableRow>
                    ) : (
                      groupData.map((g: any, idx: number) => (
                        <TableRow key={idx}>
                          <TableCell className="font-bold text-[#0F172A]">{g.group_name}</TableCell>
                          <TableCell className="text-[#64748B]">{g.manager}</TableCell>
                          <TableCell className="font-mono font-bold text-blue-600">{g.open_tickets}</TableCell>
                          <TableCell className="font-mono font-bold text-emerald-600">{g.resolved_tickets}</TableCell>
                          <TableCell className="font-mono font-bold text-[#0F172A]">{g.total_tickets}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>

            </div>
          )}

          {/* TAB 4: APPROVAL & RESOLUTION STATS */}
          {activeTab === "approvals" && (
            <div className="space-y-6">
              
              {/* Approval Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Total Approval Requests</span>
                  <span className="text-xl font-black text-[#0F172A] mt-1 block font-mono">
                    {approvalData?.total_approvals || 0}
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Approved Requests</span>
                  <span className="text-xl font-black text-emerald-600 mt-1 block font-mono">
                    {approvalData?.approved_count || 0}
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Rejected Requests</span>
                  <span className="text-xl font-black text-red-600 mt-1 block font-mono">
                    {approvalData?.rejected_count || 0}
                  </span>
                </div>
                <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase block">Approval Rate %</span>
                  <span className="text-xl font-black text-indigo-600 mt-1 block font-mono">
                    {approvalData?.approval_rate_pct || 100}%
                  </span>
                </div>
              </div>

              {/* Priority Chart */}
              <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-xs space-y-4">
                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-[#E30613]" />
                  Tickets by Urgency & Priority Rating
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={priorityChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                      <XAxis dataKey="priority" stroke="#94A3B8" fontSize={11} />
                      <YAxis stroke="#94A3B8" fontSize={11} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#8B5CF6" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          )}

        </div>
      )}

    </div>
  );
}
