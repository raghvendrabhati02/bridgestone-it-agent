/* eslint-disable */
"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback } from "react";
import {
  BarChart3, Calendar, Download, RefreshCw, Loader2, Users, FileText, CheckCircle2,
  AlertTriangle, Clock, Sparkles, BookOpen, Activity, ChevronRight, Filter, TrendingUp
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
  apiBaseUrl: string;
}

const COLORS = ["#E30613", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#14B8A6"];

export default function AnalyticsView({ user, token, apiBaseUrl }: AnalyticsViewProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState<any>(null);

  // Filter States
  const [timeFilter, setTimeFilter] = useState("month");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedDept, setSelectedDept] = useState("ALL");
  const [selectedGroup, setSelectedGroup] = useState("ALL");
  const [selectedCategory, setSelectedCategory] = useState("ALL");

  const getAuthHeaders = useCallback(() => ({
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  }), [token]);

  // Fetch Dashboard Analytics from backend
  const fetchAnalytics = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      const params = new URLSearchParams();
      params.append("time_filter", timeFilter);
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      if (selectedDept) params.append("department", selectedDept);
      if (selectedGroup) params.append("assignment_group", selectedGroup);
      if (selectedCategory) params.append("category", selectedCategory);

      const res = await apiFetch(`${apiBaseUrl}/api/analytics/dashboard?${params.toString()}`, {
        headers: getAuthHeaders()
      });

      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
      // Non-OK response: silently skip (no console noise on 401/403 during polling)
    } catch (e) {
      if (!(e instanceof NetworkError)) {
        // Unexpected error — not a connection issue
        console.warn("Analytics fetch failed:", e);
      }
      // NetworkError: silently skip, banner shown at page level
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [apiBaseUrl, getAuthHeaders, timeFilter, startDate, endDate, selectedDept, selectedGroup, selectedCategory]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // CSV Exporter
  const exportToCSV = () => {
    if (!data) return;
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF";
    
    // Header
    csvContent += "Category,Metric,Value\n";
    // Card metrics
    Object.entries(data.cards || {}).forEach(([key, val]) => {
      csvContent += `KPI,${key},${val}\n`;
    });
    // Tickets Category
    (data.charts?.tickets_by_category || []).forEach((c: any) => {
      csvContent += `Tickets Category,${c.name},${c.value}\n`;
    });
    // Tickets Department
    (data.charts?.tickets_by_department || []).forEach((c: any) => {
      csvContent += `Tickets Department,${c.name},${c.value}\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Bridgestone_ITSM_Analytics_${timeFilter}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Excel Exporter (styled XML or CSV layout with excel prefix compatibility)
  const exportToExcel = () => {
    if (!data) return;
    let excelContent = "data:text/csv;charset=utf-8,\uFEFF";
    excelContent += "Bridgestone ITSM Analytics Dashboard Report\n";
    excelContent += `Generated At: ${new Date().toLocaleString()}\n`;
    excelContent += `Filter Range: ${timeFilter}\n\n`;

    excelContent += "KPI METRICS\n";
    Object.entries(data.cards || {}).forEach(([key, val]) => {
      excelContent += `${key.replace(/_/g, " ").toUpperCase()},${val}\n`;
    });

    excelContent += "\nTICKETS BY CATEGORY\n";
    (data.charts?.tickets_by_category || []).forEach((c: any) => {
      excelContent += `${c.name},${c.value}\n`;
    });

    const encodedUri = encodeURI(excelContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Bridgestone_ITSM_Report_${timeFilter}.xls`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // PDF Exporter (Print Mode layout)
  const exportToPDF = () => {
    window.print();
  };

  const cardsInfo = data?.cards || {};
  const chartsInfo = data?.charts || {};
  const tablesInfo = data?.tables || {};

  return (
    <div className="flex-1 flex flex-col bg-[#F8FAFC] font-sans overflow-y-auto print:bg-white print:text-black">
      {/* Header */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 flex-shrink-0 print:hidden">
        <div>
          <h1 className="text-xs font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-[#E30613]" />
            Enterprise Analytics Dashboard
          </h1>
          <p className="text-[10px] text-[#64748B] font-bold uppercase mt-1 tracking-wider">Real-time IT support metrics, resolution compliance, and employee queue intelligence.</p>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <button
            onClick={() => fetchAnalytics(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Data
          </button>
          
          <button
            onClick={exportToCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-[#475569] cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            CSV
          </button>

          <button
            onClick={exportToExcel}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-gray-50 border border-gray-200 rounded-xl text-xs font-bold text-[#475569] cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            Excel
          </button>

          <button
            onClick={exportToPDF}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer"
          >
            <FileText className="w-3.5 h-3.5" />
            Export PDF
          </button>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6 max-w-7xl w-full mx-auto">
        {/* Filters Panel */}
        <div className="bg-white border border-[#E2E8F0] p-4 rounded-2xl shadow-xs space-y-3.5 print:hidden">
          <div className="flex items-center gap-2 text-xs font-bold text-gray-700">
            <Filter className="w-4 h-4 text-[#E30613]" />
            Dashboard Filters Selection
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3.5 text-xs font-bold text-gray-500">
            {/* Time Filter */}
            <div className="space-y-1">
              <label className="text-[10px] text-gray-400 block uppercase">Time Window</label>
              <select
                value={timeFilter}
                onChange={e => setTimeFilter(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-[#475569] outline-none"
              >
                <option value="today">Today</option>
                <option value="week">This Week</option>
                <option value="month">This Month</option>
                <option value="custom">Custom Date Range</option>
              </select>
            </div>

            {/* Department */}
            <div className="space-y-1">
              <label className="text-[10px] text-gray-400 block uppercase">Requester Department</label>
              <select
                value={selectedDept}
                onChange={e => setSelectedDept(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-[#475569] outline-none"
              >
                <option value="ALL">All Departments</option>
                <option value="IT Operations">IT Operations</option>
                <option value="Supply Chain & Logistics">Supply Chain &amp; Logistics</option>
                <option value="Corporate Sales">Corporate Sales</option>
                <option value="General Operations">General Operations</option>
              </select>
            </div>

            {/* Assignment Group */}
            <div className="space-y-1">
              <label className="text-[10px] text-gray-400 block uppercase">Assignment Group</label>
              <select
                value={selectedGroup}
                onChange={e => setSelectedGroup(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-[#475569] outline-none"
              >
                <option value="ALL">All Groups</option>
                <option value="Helpdesk">Helpdesk</option>
                <option value="Network">Network</option>
                <option value="Sysadmin">Sysadmin</option>
                <option value="Security">Security</option>
              </select>
            </div>

            {/* Category */}
            <div className="space-y-1">
              <label className="text-[10px] text-gray-400 block uppercase">Category</label>
              <select
                value={selectedCategory}
                onChange={e => setSelectedCategory(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-xl text-[#475569] outline-none"
              >
                <option value="ALL">All Categories</option>
                <option value="VPN">VPN</option>
                <option value="Password">Password</option>
                <option value="Software">Software</option>
                <option value="Email">Email</option>
                <option value="Network">Network</option>
                <option value="Hardware">Hardware</option>
                <option value="General">General</option>
              </select>
            </div>

            {/* Custom Dates Inputs */}
            {timeFilter === "custom" && (
              <>
                <div className="space-y-1">
                  <label className="text-[10px] text-gray-400 block uppercase font-bold">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                    className="w-full px-2.5 py-1 bg-white border border-gray-200 rounded-xl outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-gray-400 block uppercase font-bold">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                    className="w-full px-2.5 py-1 bg-white border border-gray-200 rounded-xl outline-none"
                  />
                </div>
              </>
            )}
          </div>
        </div>

        {loading ? (
          <div className="h-96 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-[#E30613] animate-spin" />
            <span className="text-xs text-gray-500 font-bold uppercase tracking-wider animate-pulse">Aggregating analytics data...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* KPI Cards Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Total Conversations", value: cardsInfo.total_conversations, icon: <Users className="w-4 h-4 text-blue-500" /> },
                { label: "Resolved by AI", value: cardsInfo.resolved_by_ai, icon: <Sparkles className="w-4 h-4 text-purple-500" /> },
                { label: "Tickets Created", value: cardsInfo.tickets_created, icon: <FileText className="w-4 h-4 text-orange-500" /> },
                { label: "Open Tickets", value: cardsInfo.open_tickets, icon: <Activity className="w-4 h-4 text-red-500" /> },
                { label: "Closed Tickets", value: cardsInfo.closed_tickets, icon: <CheckCircle2 className="w-4 h-4 text-green-500" /> },
                { label: "Avg Resolution Time", value: `${cardsInfo.avg_resolution_hours} hrs`, icon: <Clock className="w-4 h-4 text-yellow-600" /> },
                { label: "AI Resolution %", value: `${cardsInfo.ai_resolution_pct}%`, icon: <TrendingUp className="w-4 h-4 text-indigo-500" /> },
                { label: "Knowledge Base Usage", value: cardsInfo.kb_usage, icon: <BookOpen className="w-4 h-4 text-teal-500" /> },
              ].map((card, i) => (
                <div key={i} className="bg-white p-4 border border-gray-200 rounded-2xl flex items-center justify-between shadow-xs">
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">{card.label}</span>
                    <span className="text-xl font-bold text-gray-800 block">{card.value}</span>
                  </div>
                  <div className="w-8 h-8 rounded-xl bg-gray-50 flex items-center justify-center">
                    {card.icon}
                  </div>
                </div>
              ))}
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Conversations by Day */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-850 block mb-4 uppercase">Conversations by Day</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartsInfo.conversations_by_day}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Line type="monotone" dataKey="conversations" stroke="#3B82F6" strokeWidth={2} dot />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Tickets by Category */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Tickets by Category</span>
                <div className="h-64 w-full flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartsInfo.tickets_by_category} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={2} dataKey="value">
                        {(chartsInfo.tickets_by_category || []).map((e: any, idx: number) => (
                          <Cell key={`cell-${idx}`} fill={COLORS[idx % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 9 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Tickets by Department */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Tickets by Department</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartsInfo.tickets_by_department}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Bar dataKey="value" fill="#E30613" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Tickets by Assignment Group */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Tickets by Assignment Group</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartsInfo.tickets_by_assignment_group}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Bar dataKey="value" fill="#10B981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Resolution Trend */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Resolution Trend (Closed Tickets)</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartsInfo.resolution_trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Area type="monotone" dataKey="tickets" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.15} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Knowledge Usage */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Knowledge Article Queries</span>
                <div className="h-64 w-full flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={chartsInfo.knowledge_usage} cx="50%" cy="50%" innerRadius={55} outerRadius={75} paddingAngle={2} dataKey="value">
                        {(chartsInfo.knowledge_usage || []).map((e: any, idx: number) => (
                          <Cell key={`cell-${idx}`} fill={COLORS[(idx + 2) % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 9 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Top Issues */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Top Issue Descriptions</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={chartsInfo.top_issues}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                      <XAxis type="number" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 8 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Bar dataKey="value" fill="#F59E0B" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Engineer Performance */}
              <div className="bg-white border border-gray-200 p-5 rounded-2xl shadow-xs">
                <span className="text-xs font-bold text-gray-855 block mb-4 uppercase">Engineer Performance (Resolved Counts)</span>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartsInfo.engineer_performance}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                      <Bar dataKey="tickets" fill="#EC4899" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Tables Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Tickets Table */}
              <div className="bg-white border border-gray-200 rounded-2xl shadow-xs overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                  <span className="text-[10px] font-bold text-gray-400 block uppercase">Recent Support Tickets</span>
                </div>
                <div className="overflow-x-auto text-[11px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Requester</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(tablesInfo.recent_tickets || []).map((t: any) => (
                        <TableRow key={t.ticket_id}>
                          <TableCell className="font-mono font-bold text-[#1E293B]">{t.ticket_id}</TableCell>
                          <TableCell className="font-semibold text-[#1E293B]">{t.created_by}</TableCell>
                          <TableCell className="text-[#475569]">{t.category}</TableCell>
                          <TableCell>
                            <PriorityPill priority={t.priority} />
                          </TableCell>
                          <TableCell>
                            <StatusPill status={t.status} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Recent Conversations Table */}
              <div className="bg-white border border-gray-200 rounded-2xl shadow-xs overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                  <span className="text-[10px] font-bold text-gray-400 block uppercase">Recent Portal Chat Sessions</span>
                </div>
                <div className="overflow-x-auto text-[11px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Session ID</TableHead>
                        <TableHead>Employee</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(tablesInfo.recent_conversations || []).map((s: any) => (
                        <TableRow key={s.session_id}>
                          <TableCell className="font-mono font-bold text-[#1E293B] truncate max-w-[120px]">{s.session_id}</TableCell>
                          <TableCell className="font-semibold text-[#1E293B]">{s.username}</TableCell>
                          <TableCell className="text-[#475569]">{new Date(s.created_at).toLocaleDateString()}</TableCell>
                          <TableCell>
                            <StatusPill status={s.status} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Top Employees Table */}
              <div className="bg-white border border-gray-200 rounded-2xl shadow-xs overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                  <span className="text-[10px] font-bold text-gray-400 block uppercase">Top Requesters</span>
                </div>
                <div className="overflow-x-auto text-[11px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Username</TableHead>
                        <TableHead>Department</TableHead>
                        <TableHead>Workforce Tickets Count</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(tablesInfo.top_employees || []).map((e: any) => (
                        <TableRow key={e.username}>
                          <TableCell className="font-semibold text-[#1E293B]">{e.username}</TableCell>
                          <TableCell className="text-[#475569]">{e.department}</TableCell>
                          <TableCell className="text-[#0F172A] font-bold">{e.tickets_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>

              {/* Top Knowledge Articles Table */}
              <div className="bg-white border border-gray-200 rounded-2xl shadow-xs overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                  <span className="text-[10px] font-bold text-gray-400 block uppercase">Top KB Troubleshooting Guides</span>
                </div>
                <div className="overflow-x-auto text-[11px]">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Article ID</TableHead>
                        <TableHead>Title</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead>Total consults</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(tablesInfo.top_knowledge_articles || []).map((a: any) => (
                        <TableRow key={a.id}>
                          <TableCell className="font-mono font-bold text-[#1E293B]">{a.id}</TableCell>
                          <TableCell className="font-semibold text-[#1E293B]">{a.title}</TableCell>
                          <TableCell className="text-[#475569]">{a.category}</TableCell>
                          <TableCell className="text-[#0F172A] font-bold">{a.use_count} times</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
