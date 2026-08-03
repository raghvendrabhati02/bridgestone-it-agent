"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Sparkles, Clock, CheckCircle2, XCircle, History, User,
  LayoutDashboard, Filter, FileText, ChevronRight,
  Check, X, ShieldAlert, Send, Loader2, Download, ChevronLeft,
  ChevronRight as ChevronRightIcon, Paperclip, Shield, AlertCircle
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Cell, Legend
} from "recharts";
import {
  SearchInput,
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  StatusPill,
  PriorityPill,
  RequestTypePill,
  ApprovalPill
} from "./shared/UIComponents";
import TicketDetailsModal from "./TicketDetailsModal";

// ─────────────────────────────────────────────────────────────────────────────
// Interfaces
// ─────────────────────────────────────────────────────────────────────────────
interface ManagerTicket {
  ticket_id: string;
  category: string;
  description: string;
  issue_description?: string;
  assigned_team: string;
  assigned_engineer?: string;
  priority?: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at?: string;
  resolved_at?: string;
  closed_at?: string;
  requires_approval?: boolean;
  request_type?: string;
  manager?: string;
  approved_by?: string;
  approved_at?: string;
  approval_notes?: string;
  software_requested?: string;
  approval_status?: string;
  assignment_group?: string;
  sla_hours?: number;
  sla_state?: string;
  sla_breached?: boolean;
  ai_recommendation?: string;
}

interface TimelineEvent {
  id: number;
  event_type: string;
  actor: string;
  action: string;
  description: string;
  created_at: string;
}

interface Comment {
  id: number;
  author: string;
  text: string;
  created_at: string;
  is_internal: boolean;
}

interface ManagerPortalProps {
  user: any;
  token: string | null;
}

type SubView = "dashboard" | "pending" | "approved" | "rejected" | "history" | "profile";

const CHART_COLORS = ["#E30613", "#2563EB", "#06B6D4", "#16A34A", "#F59E0B", "#7C3AED"];

export default function ManagerPortal({ user, token }: ManagerPortalProps) {
  // Navigation
  const [subView, setSubView] = useState<SubView>("dashboard");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  
  // Data State
  const [allTickets, setAllTickets] = useState<ManagerTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState<ManagerTicket | null>(null);
  
  // Details Panel State
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [actionReason, setActionReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  // Notification Toast
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch Tickets
  const fetchTickets = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      const res = await apiFetch("/api/itsm/manager-tickets?approval_status=ALL", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setAllTickets(data.tickets || []);
      } else {
        showToast("Failed to fetch tickets", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network error fetching requests", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  // Phase 6.3: Auto-refresh every 10 seconds so new approval requests appear without manual refresh.
  useEffect(() => {
    const intervalId = setInterval(() => {
      fetchTickets(true); // silent refresh
    }, 10000);
    return () => clearInterval(intervalId);
  }, [fetchTickets]);

  // Fetch comments & timeline on ticket select
  const fetchTicketDetails = async (ticketId: string) => {
    setCommentsLoading(true);
    setTimelineLoading(true);
    try {
      const timeRes = await apiFetch(`/tickets/${ticketId}/timeline`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (timeRes.ok) {
        const timeData = await timeRes.json();
        // Backend returns a plain array
        setTimeline(Array.isArray(timeData) ? timeData : (timeData.timeline || []));
      }

      const commRes = await apiFetch(`/tickets/${ticketId}/comments`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (commRes.ok) {
        const commData = await commRes.json();
        // Backend returns a plain array
        setComments(Array.isArray(commData) ? commData : (commData.comments || []));
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    } finally {
      setCommentsLoading(false);
      setTimelineLoading(false);
    }
  };

  const handleTicketClick = (ticket: ManagerTicket) => {
    setSelectedTicket(ticket);
    setActionReason("");
    fetchTicketDetails(ticket.ticket_id);
  };

  // POST comment helper
  const handlePostComment = async () => {
    if (!newComment.trim() || !selectedTicket) return;
    try {
      const res = await apiFetch(`/tickets/${selectedTicket.ticket_id}/comments`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          text: newComment,
          is_internal: false
        })
      });

      if (res.ok) {
        setNewComment("");
        const commRes = await apiFetch(`/tickets/${selectedTicket.ticket_id}/comments`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (commRes.ok) {
          const commData = await commRes.json();
          // Backend returns a plain array
          setComments(Array.isArray(commData) ? commData : (commData.comments || []));
        }
      }
    } catch (e) {
      showToast("Failed to post comment", "error");
    }
  };

  // Approval action helper
  const handleApprove = async () => {
    if (!selectedTicket) return;
    setActionLoading(true);
    try {
      const res = await apiFetch(`/api/itsm/manager-tickets/${selectedTicket.ticket_id}/approve`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          reason: actionReason || "Approved via Manager Portal.",
          notes: actionReason || ""
        })
      });

      if (res.ok) {
        showToast("✅ Request approved. Ticket moved to Admin Queue (READY FOR ADMIN).");
        setSelectedTicket(null);
        setActionReason("");
        fetchTickets(true);
      } else {
        const errData = await res.json();
        showToast(errData.detail || "Approval action failed.", "error");
      }
    } catch (e) {
      showToast("Connection failure during approval.", "error");
    } finally {
      setActionLoading(false);
    }
  };

  // Rejection action helper
  const handleReject = async () => {
    if (!selectedTicket) return;
    if (!actionReason.trim()) {
      showToast("You must provide a comment explanation for rejecting requests.", "error");
      return;
    }
    setActionLoading(true);
    try {
      const res = await apiFetch(`/tickets/${selectedTicket.ticket_id}/action`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          action: "manager_reject",
          note: actionReason
        })
      });

      if (res.ok) {
        showToast("Ticket request rejected successfully.");
        setSelectedTicket(null);
        fetchTickets(true);
      } else {
        const errData = await res.json();
        showToast(errData.detail || "Rejection action failed.", "error");
      }
    } catch (e) {
      showToast("Connection failure during rejection.", "error");
    } finally {
      setActionLoading(false);
    }
  };

  // Compute stats metrics dynamically
  const stats = useMemo(() => {
    let pending = 0;
    let approvedToday = 0;
    let rejectedToday = 0;
    let totalApprovalTimeSec = 0;
    let countApprovedOrRejected = 0;

    const todayStr = new Date().toISOString().split("T")[0];

    allTickets.forEach(t => {
      if (t.approval_status === "PENDING") {
        pending++;
      } else if (t.approval_status === "APPROVED") {
        const updateDate = t.updated_at ? t.updated_at.split("T")[0] : "";
        if (updateDate === todayStr) {
          approvedToday++;
        }
        if (t.created_at && t.updated_at) {
          const diff = new Date(t.updated_at).getTime() - new Date(t.created_at).getTime();
          totalApprovalTimeSec += diff / 1000;
          countApprovedOrRejected++;
        }
      } else if (t.approval_status === "REJECTED") {
        const updateDate = t.updated_at ? t.updated_at.split("T")[0] : "";
        if (updateDate === todayStr) {
          rejectedToday++;
        }
        if (t.created_at && t.updated_at) {
          const diff = new Date(t.updated_at).getTime() - new Date(t.created_at).getTime();
          totalApprovalTimeSec += diff / 1000;
          countApprovedOrRejected++;
        }
      }
    });

    const avgMin = countApprovedOrRejected > 0 
      ? Math.round((totalApprovalTimeSec / countApprovedOrRejected) / 60)
      : 14;

    return {
      pending,
      approvedToday,
      rejectedToday,
      avgApprovalTime: `${avgMin} mins`
    };
  }, [allTickets]);

  // Chart Data: Approvals by Day
  const approvalsByDayData = useMemo(() => {
    const last7Days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - i);
      return d.toISOString().split("T")[0];
    }).reverse();

    const counts: Record<string, number> = {};
    last7Days.forEach(day => { counts[day] = 0; });

    allTickets.forEach(t => {
      if (t.approval_status === "APPROVED" && t.updated_at) {
        const dStr = t.updated_at.split("T")[0];
        if (dStr in counts) {
          counts[dStr]++;
        }
      }
    });

    return last7Days.map(day => {
      const [_, m, d] = day.split("-");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthLabel = months[parseInt(m) - 1] || m;
      return {
        date: `${monthLabel} ${parseInt(d)}`,
        Approvals: counts[day]
      };
    });
  }, [allTickets]);

  // Chart Data: Requests by Category
  const categoryChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    allTickets.forEach(t => {
      const cat = t.category || "General";
      counts[cat] = (counts[cat] || 0) + 1;
    });

    return Object.entries(counts).map(([name, value]) => ({
      name: name.replace(/_/g, " "),
      value
    }));
  }, [allTickets]);

  // Filtering Logic
  const filteredList = useMemo(() => {
    return allTickets.filter(t => {
      const query = searchQuery.toLowerCase();
      const matchesSearch = !query || 
        t.ticket_id.toLowerCase().includes(query) ||
        t.category.toLowerCase().includes(query) ||
        t.created_by.toLowerCase().includes(query) ||
        (t.description || "").toLowerCase().includes(query);

      const matchesPriority = priorityFilter === "ALL" || t.priority === priorityFilter;
      const matchesType = typeFilter === "ALL" || t.request_type === typeFilter;
      
      let matchesDate = true;
      if (startDate) {
        matchesDate = matchesDate && new Date(t.created_at) >= new Date(startDate);
      }
      if (endDate) {
        const endLimit = new Date(endDate);
        endLimit.setDate(endLimit.getDate() + 1);
        matchesDate = matchesDate && new Date(t.created_at) < endLimit;
      }

      let matchesView = true;
      if (subView === "pending") {
        matchesView = t.approval_status === "PENDING";
      } else if (subView === "approved") {
        matchesView = t.approval_status === "APPROVED";
      } else if (subView === "rejected") {
        matchesView = t.approval_status === "REJECTED";
      }

      return matchesSearch && matchesPriority && matchesType && matchesDate && matchesView;
    });
  }, [allTickets, searchQuery, priorityFilter, typeFilter, startDate, endDate, subView]);

  // Pagination Helper
  const paginatedList = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredList.slice(start, start + itemsPerPage);
  }, [filteredList, currentPage]);

  const totalPages = Math.ceil(filteredList.length / itemsPerPage) || 1;

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, priorityFilter, typeFilter, startDate, endDate, subView]);

  // Export CSV
  const handleExportCSV = () => {
    if (filteredList.length === 0) {
      showToast("No data to export", "error");
      return;
    }
    const headers = ["Ticket ID", "Category", "Request Type", "Priority", "Status", "Approval Status", "Created By", "Created At", "Description"];
    const rows = filteredList.map(t => [
      t.ticket_id,
      t.category,
      t.request_type || "SERVICE_REQUEST",
      t.priority || "MEDIUM",
      t.status,
      t.approval_status || "PENDING",
      t.created_by,
      t.created_at,
      (t.description || t.issue_description || "").replace(/"/g, '""')
    ]);

    const csvContent = "data:text/csv;charset=utf-8," 
      + [headers.join(","), ...rows.map(e => e.map(val => `"${val}"`).join(","))].join("\n");
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Manager_Approvals_Export_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast("CSV Exported successfully", "success");
  };

  // Workflow stage progression helpers
  const getWorkflowStages = (ticket: ManagerTicket) => {
    const status = ticket.status?.toUpperCase() || "";
    const stages = [
      { label: "Request Submitted",    done: true },
      { label: "Manager Approval",     done: ["READY_FOR_ADMIN","WAITING_ADMIN","ACCESS_GRANTED","COMPLETED","APPROVED"].includes(status), active: ["WAITING_MANAGER","WAITING_MANAGER_APPROVAL"].includes(status) },
      { label: "Admin Access Grant",   done: ["ACCESS_GRANTED","COMPLETED"].includes(status), active: status === "READY_FOR_ADMIN" },
      { label: "Installation",         done: status === "COMPLETED", active: status === "ACCESS_GRANTED" },
      { label: "Completed",            done: status === "COMPLETED" },
    ];
    return stages;
  };

  return (
    <div className="flex h-full w-full bg-[#F8FAFC] font-sans overflow-hidden">
      
      {/* Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-55 flex items-center gap-2 px-4 py-3 rounded-xl border shadow-xl bg-white border-[#E2E8F0] max-w-sm">
          {toast.type === "success" ? <CheckCircle2 className="w-5 h-5 text-[#16A34A]" /> : <AlertCircle className="w-5 h-5 text-[#DC2626]" />}
          <span className="text-xs font-semibold text-[#1E293B]">{toast.msg}</span>
        </div>
      )}

      {/* Mobile Drawer Overlay Backdrop */}
      {isSidebarOpen && (
        <div
          onClick={() => setIsSidebarOpen(false)}
          className="md:hidden fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-30 transition-opacity"
        />
      )}

      {/* Mobile Sidebar Drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 bg-white border-r border-[#E2E8F0] flex flex-col pt-3 pb-4 shadow-xl transform transition-transform duration-300 ease-in-out md:hidden ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-4 pb-3 border-b border-[#F1F5F9] mb-2">
          <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider">Manager Navigation</span>
          <button
            onClick={() => setIsSidebarOpen(false)}
            className="p-1 rounded-lg text-[#64748B] hover:bg-[#F1F5F9] cursor-pointer"
            aria-label="Close navigation"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {[
            { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
            { id: "pending", label: "Pending Approvals", icon: <Clock className="w-4 h-4" />, badge: stats.pending },
            { id: "approved", label: "Approved Requests", icon: <CheckCircle2 className="w-4 h-4" /> },
            { id: "rejected", label: "Rejected Requests", icon: <XCircle className="w-4 h-4" /> },
            { id: "history", label: "Request History", icon: <History className="w-4 h-4" /> },
            { id: "profile", label: "Manager Profile", icon: <User className="w-4 h-4" /> },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setSubView(item.id as SubView);
                setSelectedTicket(null);
                setIsSidebarOpen(false); // Auto close
              }}
              className={`w-full flex items-center justify-between px-3 py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer
                ${subView === item.id 
                  ? "bg-red-50 text-[#E30613]" 
                  : "text-[#475569] hover:text-[#0F172A] hover:bg-[#F8FAFC]"}`}
            >
              <div className="flex items-center gap-2.5">
                {item.icon}
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[#E30613] text-white">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </aside>

      {/* LEFT SIDEBAR (DESKTOP) */}
      <aside className="w-60 bg-white border-r border-[#E2E8F0] hidden md:flex flex-col flex-shrink-0">
        <nav className="flex-1 px-3 py-4 space-y-1">
          {[
            { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
            { id: "pending", label: "Pending Approvals", icon: <Clock className="w-4 h-4" />, badge: stats.pending },
            { id: "approved", label: "Approved Requests", icon: <CheckCircle2 className="w-4 h-4" /> },
            { id: "rejected", label: "Rejected Requests", icon: <XCircle className="w-4 h-4" /> },
            { id: "history", label: "Request History", icon: <History className="w-4 h-4" /> },
            { id: "profile", label: "Manager Profile", icon: <User className="w-4 h-4" /> },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => { setSubView(item.id as SubView); setSelectedTicket(null); }}
              className={`w-full flex items-center justify-between px-3 py-2 text-xs font-semibold rounded-xl transition-all cursor-pointer
                ${subView === item.id 
                  ? "bg-red-50 text-[#E30613]" 
                  : "text-[#475569] hover:text-[#0F172A] hover:bg-[#F8FAFC]"}`}
            >
              <div className="flex items-center gap-2.5">
                {item.icon}
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[#E30613] text-white">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        {/* User Info footer */}
        <div className="p-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center font-bold text-[#E30613] text-xs">
              M
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-[#0F172A] block truncate">
                {user?.username ? user.username.charAt(0).toUpperCase() + user.username.slice(1) : "Manager"}
              </span>
              <span className="text-[9px] text-[#64748B] font-semibold block uppercase">
                {user?.role || "MANAGER"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Top Header */}
        <header className="h-12 bg-white border-b border-[#E2E8F0] flex items-center justify-between px-6 flex-shrink-0 z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
              title="Open menu options"
              aria-label="Open menu options"
            >
              <Filter className="w-3.5 h-3.5" />
            </button>
            <h2 className="text-xs font-black text-[#0F172A] uppercase tracking-wider">
              Manager approvals: {subView.replace(/_/g, " ")}
            </h2>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => fetchTickets(true)}
              disabled={refreshing}
              className="p-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] cursor-pointer disabled:opacity-50"
              title="Refresh requests list"
            >
              {refreshing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <History className="w-3.5 h-3.5" />}
            </button>
          </div>
        </header>

        {/* Scrollable Panel content */}
        <div className="flex-1 overflow-y-auto p-6 min-h-0 flex flex-col lg:flex-row gap-6 relative">
          
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 text-[#E30613] animate-spin" />
              <span className="text-xs font-bold text-[#64748B]">Loading Manager Portal data...</span>
            </div>
          ) : (
            <div className="flex-1 min-w-0 space-y-6">
              
              {/* SUBVIEW: DASHBOARD */}
              {subView === "dashboard" && (
                <div className="space-y-6">
                  {/* Stat Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { label: "Pending Approvals", value: stats.pending, icon: <Clock className="w-4 h-4 text-orange-655" />, border: "border-orange-200 bg-orange-50/30" },
                      { label: "Approved Today", value: stats.approvedToday, icon: <CheckCircle2 className="w-4 h-4 text-green-655" />, border: "border-green-200 bg-green-50/30" },
                      { label: "Rejected Today", value: stats.rejectedToday, icon: <XCircle className="w-4 h-4 text-red-655" />, border: "border-red-200 bg-red-50/30" },
                      { label: "Avg Approval Time", value: stats.avgApprovalTime, icon: <Sparkles className="w-4 h-4 text-purple-655" />, border: "border-purple-200 bg-purple-50/30" },
                    ].map((card, i) => (
                      <div key={i} className={`bg-white p-4 border rounded-2xl flex items-center justify-between shadow-xs ${card.border}`}>
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold text-[#64748B] uppercase block tracking-wider">{card.label}</span>
                          <span className="text-lg font-bold text-[#0F172A] block">{card.value}</span>
                        </div>
                        <div className="w-8 h-8 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-center">
                          {card.icon}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Charts row */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Approvals by Day</span>
                      <div className="h-64 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={approvalsByDayData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                            <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#94a3b8" />
                            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" />
                            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                            <Bar dataKey="Approvals" fill="#E30613" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Requests by Category</span>
                      <div className="h-64 w-full flex items-center justify-center">
                        {categoryChartData.length === 0 ? (
                          <span className="text-xs text-[#94A3B8] italic">No category data available</span>
                        ) : (
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={categoryChartData}
                                cx="50%"
                                cy="50%"
                                labelLine={false}
                                outerRadius={80}
                                fill="#8884d8"
                                dataKey="value"
                              >
                                {categoryChartData.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                ))}
                              </Pie>
                              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                              <Legend wrapperStyle={{ fontSize: 11 }} />
                            </PieChart>
                          </ResponsiveContainer>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Quick Overview Table */}
                  <div className="space-y-2">
                    <span className="text-[10px] font-black text-[#64748B] uppercase tracking-wider block">Awaiting Manager Approvals</span>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {["Ticket ID", "Employee", "Category", "Priority", "Created", "Status", ""].map(h => (
                            <TableHead key={h}>{h}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {allTickets.filter(t => t.approval_status === "PENDING").slice(0, 5).map(t => (
                          <TableRow key={t.ticket_id}>
                            <TableCell className="font-mono font-bold text-[#1E293B]">{t.ticket_id}</TableCell>
                            <TableCell className="font-semibold text-[#1E293B]">{t.created_by}</TableCell>
                            <TableCell className="text-[#475569]">{t.category.replace(/_/g, " ")}</TableCell>
                            <TableCell>
                              <PriorityPill priority={t.priority || "MEDIUM"} />
                            </TableCell>
                            <TableCell className="text-[#64748B]">{new Date(t.created_at).toLocaleDateString()}</TableCell>
                            <TableCell>
                              <ApprovalPill status={t.approval_status || "PENDING"} />
                            </TableCell>
                            <TableCell className="text-right">
                              <button 
                                onClick={() => handleTicketClick(t)} 
                                className="px-2.5 py-1 text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl font-bold text-[10.5px] cursor-pointer border border-[#E2E8F0] shadow-xs"
                              >
                                Inspect
                              </button>
                            </TableCell>
                          </TableRow>
                        ))}
                        {allTickets.filter(t => t.approval_status === "PENDING").length === 0 && (
                          <TableRow>
                            <TableCell colSpan={7} className="p-8 text-center text-[#94A3B8] italic font-semibold">
                              All requests resolved. Zero pending approvals.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* SUBVIEWS: PENDING / APPROVED / REJECTED */}
              {(subView === "pending" || subView === "approved" || subView === "rejected") && (
                <div className="space-y-4">
                  <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
                    <span className="text-[10px] font-black text-[#64748B] uppercase tracking-wider block">
                      {subView === "pending" && "Pending Approvals Table"}
                      {subView === "approved" && "Approved Requests"}
                      {subView === "rejected" && "Rejected Requests"}
                    </span>
                    <div className="w-64">
                      <SearchInput
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search requester..."
                      />
                    </div>
                  </div>

                  {filteredList.length === 0 ? (
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-12 text-center text-[#94A3B8] italic font-semibold">
                      No requests found matching your filter parameters.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {subView === "approved" ? (
                            ["Ticket ID", "Employee", "Software Requested", "Approved By", "Approval Time", "Approval Notes", "Status", ""].map(h => (
                              <TableHead key={h}>{h}</TableHead>
                            ))
                          ) : (
                            ["Ticket ID", "Employee", "Request Type", "Category", "Priority", "Created", "Status", ""].map(h => (
                              <TableHead key={h}>{h}</TableHead>
                            ))
                          )}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredList.map(t => (
                          <TableRow key={t.ticket_id}>
                            <TableCell className="font-mono font-bold text-[#1E293B]">{t.ticket_id}</TableCell>
                            <TableCell className="font-semibold text-[#1E293B]">{t.created_by}</TableCell>
                            {subView === "approved" ? (
                              <>
                                <TableCell className="font-bold text-indigo-700">{t.software_requested || t.category}</TableCell>
                                <TableCell className="font-semibold text-[#0F172A]">{t.approved_by || t.manager || "manager"}</TableCell>
                                <TableCell className="text-[#64748B]">{new Date(t.approved_at || t.updated_at || t.created_at).toLocaleString()}</TableCell>
                                <TableCell className="text-[#475569] max-w-[200px] truncate">{t.approval_notes || "Approved"}</TableCell>
                                <TableCell>
                                  <ApprovalPill status="APPROVED" />
                                </TableCell>
                              </>
                            ) : (
                              <>
                                <TableCell>
                                  <RequestTypePill type={t.request_type || "SERVICE_REQUEST"} />
                                </TableCell>
                                <TableCell className="text-[#475569]">{t.category.replace(/_/g, " ")}</TableCell>
                                <TableCell>
                                  <PriorityPill priority={t.priority || "MEDIUM"} />
                                </TableCell>
                                <TableCell className="text-[#64748B]">{new Date(t.created_at).toLocaleString()}</TableCell>
                                <TableCell>
                                  <StatusPill status={t.status} />
                                </TableCell>
                              </>
                            )}
                            <TableCell className="text-right">
                              <button 
                                onClick={() => handleTicketClick(t)} 
                                className="px-2.5 py-1 text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl font-bold text-[10.5px] cursor-pointer border border-[#E2E8F0] shadow-xs"
                              >
                                Inspect
                              </button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              )}

              {/* SUBVIEW: REQUEST HISTORY */}
              {subView === "history" && (
                <div className="space-y-4">
                  {/* Filters block */}
                  <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <span className="text-[10px] font-black text-[#64748B] uppercase tracking-wider block">Search &amp; Filter Requests</span>
                      <button 
                        onClick={handleExportCSV} 
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer shadow-xs"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Export CSV
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3.5">
                      <SearchInput
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search request..."
                      />

                      <select
                        value={priorityFilter}
                        onChange={e => setPriorityFilter(e.target.value)}
                        className="px-3 py-1.5 w-full rounded-xl border border-[#E2E8F0] text-xs bg-white text-[#475569] font-bold focus:outline-none focus:border-[#E30613]"
                      >
                        <option value="ALL">All Priorities</option>
                        <option value="LOW">Low</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HIGH">High</option>
                        <option value="CRITICAL">Critical</option>
                      </select>

                      <select
                        value={typeFilter}
                        onChange={e => setTypeFilter(e.target.value)}
                        className="px-3 py-1.5 w-full rounded-xl border border-[#E2E8F0] text-xs bg-white text-[#475569] font-bold focus:outline-none focus:border-[#E30613]"
                      >
                        <option value="ALL">All Request Types</option>
                        <option value="SERVICE_REQUEST">Service Request</option>
                        <option value="PRIVILEGED_ACTION">Privileged Action</option>
                      </select>

                      <div className="flex items-center gap-1.5 bg-white px-3 py-1 rounded-xl border border-[#E2E8F0] text-[10px] font-bold text-[#64748B]">
                        <span className="uppercase tracking-wider">From:</span>
                        <input
                          type="date"
                          value={startDate}
                          onChange={e => setStartDate(e.target.value)}
                          className="w-full text-xs bg-transparent border-0 outline-none text-[#334155] font-semibold"
                        />
                      </div>

                      <div className="flex items-center gap-1.5 bg-white px-3 py-1 rounded-xl border border-[#E2E8F0] text-[10px] font-bold text-[#64748B]">
                        <span className="uppercase tracking-wider">To:</span>
                        <input
                          type="date"
                          value={endDate}
                          onChange={e => setEndDate(e.target.value)}
                          className="w-full text-xs bg-transparent border-0 outline-none text-[#334155] font-semibold"
                        />
                      </div>
                    </div>
                  </div>

                  {paginatedList.length === 0 ? (
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-12 text-center text-[#94A3B8] italic font-semibold">
                      No historical requests match filters.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {["Ticket ID", "Employee", "Category", "Priority", "Created", "Status", "Approval", ""].map(h => (
                            <TableHead key={h}>{h}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedList.map(t => (
                          <TableRow key={t.ticket_id}>
                            <TableCell className="font-mono font-bold text-[#1E293B]">{t.ticket_id}</TableCell>
                            <TableCell className="font-semibold text-[#1E293B]">{t.created_by}</TableCell>
                            <TableCell className="text-[#475569]">{t.category.replace(/_/g, " ")}</TableCell>
                            <TableCell>
                              <PriorityPill priority={t.priority || "MEDIUM"} />
                            </TableCell>
                            <TableCell className="text-[#64748B]">{new Date(t.created_at).toLocaleString()}</TableCell>
                            <TableCell>
                              <StatusPill status={t.status} />
                            </TableCell>
                            <TableCell>
                              <ApprovalPill status={t.approval_status || "PENDING"} />
                            </TableCell>
                            <TableCell className="text-right">
                              <button 
                                onClick={() => handleTicketClick(t)} 
                                className="px-2.5 py-1 text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl font-bold text-[10.5px] cursor-pointer border border-[#E2E8F0] shadow-xs"
                              >
                                View
                              </button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}

                  {/* Pagination footer */}
                  {filteredList.length > itemsPerPage && (
                    <div className="p-4 border border-[#E2E8F0] rounded-xl bg-white flex items-center justify-between">
                      <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">
                        Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, filteredList.length)} of {filteredList.length}
                      </span>
                      <div className="flex gap-2">
                        <button
                          disabled={currentPage === 1}
                          onClick={() => setCurrentPage(c => Math.max(c - 1, 1))}
                          className="p-1.5 border border-[#E2E8F0] rounded-xl disabled:opacity-40 cursor-pointer hover:bg-[#F8FAFC] transition-colors"
                        >
                          <ChevronLeft className="w-3.5 h-3.5 text-[#475569]" />
                        </button>
                        <button
                          disabled={currentPage === totalPages}
                          onClick={() => setCurrentPage(c => Math.min(c + 1, totalPages))}
                          className="p-1.5 border border-[#E2E8F0] rounded-xl disabled:opacity-40 cursor-pointer hover:bg-[#F8FAFC] transition-colors"
                        >
                          <ChevronRightIcon className="w-3.5 h-3.5 text-[#475569]" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* SUBVIEW: PROFILE */}
              {subView === "profile" && (
                <div className="max-w-2xl bg-white border border-[#E2E8F0] rounded-2xl shadow-xs overflow-hidden p-6 space-y-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-red-100 flex items-center justify-center font-bold text-[#E30613] text-2xl shadow-xs border border-[#FEE2E2]">
                      {user?.username ? user.username.charAt(0).toUpperCase() : "M"}
                    </div>
                    <div>
                      <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                        {user?.username ? user.username.charAt(0).toUpperCase() + user.username.slice(1) : "Manager"}
                      </h3>
                      <span className="text-[10px] text-[#64748B] font-bold uppercase block tracking-wider mt-1">IT Infrastructure &amp; Security Manager</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-[#E2E8F0] text-xs font-bold uppercase tracking-wider">
                    <div className="bg-[#F8FAFC] p-3 rounded-xl space-y-0.5 border border-[#E2E8F0]">
                      <span className="text-[9px] text-[#64748B] font-bold block">Role Hierarchy</span>
                      <span className="text-[#0F172A] block">{user?.role || "IT MANAGER (L2 Support Approver)"}</span>
                    </div>
                    <div className="bg-[#F8FAFC] p-3 rounded-xl space-y-0.5 border border-[#E2E8F0]">
                      <span className="text-[9px] text-[#64748B] font-bold block">Department</span>
                      <span className="text-[#0F172A] block">Bridgestone Corporate IT</span>
                    </div>
                    <div className="bg-[#F8FAFC] p-3 rounded-xl space-y-0.5 border border-[#E2E8F0]">
                      <span className="text-[9px] text-[#64748B] font-bold block">Approval Limit</span>
                      <span className="text-[#0F172A] block">All Service Catalog Items</span>
                    </div>
                    <div className="bg-[#F8FAFC] p-3 rounded-xl space-y-0.5 border border-[#E2E8F0]">
                      <span className="text-[9px] text-[#64748B] font-bold block">Signing Delegation</span>
                      <span className="text-[#0F172A] block">Active Gateway / AD Integrations</span>
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}

          {/* DETAIL DRAWER / OVERLAY PANEL */}
          {selectedTicket && (
            <div className="w-full lg:w-[480px] bg-white border border-[#E2E8F0] rounded-2xl flex flex-col shadow-lg overflow-hidden flex-shrink-0 z-20 h-[calc(100vh-80px)] lg:h-auto font-sans">
              {/* Drawer Header */}
              <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
                <div>
                  <h3 className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5 uppercase tracking-wider">
                    <FileText className="w-4 h-4 text-indigo-500" />
                    Request Details
                  </h3>
                  <span className="text-[10px] font-mono text-[#64748B] block mt-0.5">{selectedTicket.ticket_id}</span>
                </div>
                <button
                  onClick={() => setSelectedTicket(null)}
                  className="p-1.5 hover:bg-[#F1F5F9] rounded-lg text-[#94A3B8] hover:text-[#475569] transition cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Drawer Scrollable Content */}
              <div className="flex-1 overflow-y-auto p-5 space-y-5">

                {/* Phase 6.3: Workflow Stage Tracker */}
                <div className="bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700 p-4 rounded-xl space-y-3">
                  <span className="text-[9px] text-slate-400 block font-bold uppercase tracking-wider">Approval Workflow Progress</span>
                  <div className="flex items-center gap-1">
                    {selectedTicket && getWorkflowStages(selectedTicket).map((stage, i, arr) => (
                      <>
                        <div key={stage.label} className="flex flex-col items-center gap-1 min-w-0">
                          <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 border-2 ${
                            stage.done    ? "bg-emerald-500 border-emerald-400" :
                            stage.active  ? "bg-amber-400 border-amber-300 animate-pulse" :
                            "bg-slate-700 border-slate-600"
                          }`}>
                            {stage.done ? (
                              <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                            ) : (
                              <span className="w-1.5 h-1.5 rounded-full bg-current" style={{ color: stage.active ? "#fbbf24" : "#64748b" }} />
                            )}
                          </div>
                          <span className={`text-[8px] font-bold text-center leading-tight max-w-[52px] ${
                            stage.done ? "text-emerald-400" : stage.active ? "text-amber-300" : "text-slate-500"
                          }`}>{stage.label}</span>
                        </div>
                        {i < arr.length - 1 && (
                          <div className={`flex-1 h-0.5 mb-4 ${
                            arr[i+1].done || arr[i+1].active ? "bg-emerald-500" : "bg-slate-700"
                          }`} />
                        )}
                      </>
                    ))}
                  </div>
                </div>

                {/* Ticket ID + Status Banner */}
                <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5">
                  <div>
                    <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider block">Ticket ID</span>
                    <span className="font-mono font-bold text-slate-900 text-xs">{selectedTicket.ticket_id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <ApprovalPill status={selectedTicket.approval_status || "PENDING"} />
                    <StatusPill status={selectedTicket.status} />
                  </div>
                </div>

                {/* Approved Manager Summary Card */}
                {selectedTicket.approval_status === "APPROVED" && (
                  <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-xl space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        Manager Approval History
                      </span>
                      <ApprovalPill status="APPROVED" />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-emerald-200/60 font-semibold text-emerald-950">
                      <div><span className="text-emerald-700 text-[10px] uppercase font-bold block">Approved By:</span>{selectedTicket.approved_by || selectedTicket.manager || "manager"}</div>
                      <div><span className="text-emerald-700 text-[10px] uppercase font-bold block">Approval Time:</span>{new Date(selectedTicket.approved_at || selectedTicket.updated_at || selectedTicket.created_at).toLocaleString()}</div>
                      <div><span className="text-emerald-700 text-[10px] uppercase font-bold block">Employee:</span>{selectedTicket.created_by}</div>
                      <div><span className="text-emerald-700 text-[10px] uppercase font-bold block">Software Requested:</span>{selectedTicket.software_requested || selectedTicket.category}</div>
                    </div>
                    <div className="pt-1.5 border-t border-emerald-200/60 text-xs">
                      <span className="text-emerald-700 text-[10px] uppercase font-bold block">Approval Notes:</span>
                      <p className="text-emerald-950 italic font-medium">{selectedTicket.approval_notes || "Approved via Manager Portal."}</p>
                    </div>
                  </div>
                )}
                <div className="space-y-2 bg-[#F8FAFC] border border-[#E2E8F0] p-3.5 rounded-xl">
                  <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Employee Information</span>
                  <div className="text-xs space-y-1 font-bold uppercase">
                    <div className="flex justify-between"><span className="text-[#64748B]">Name:</span><span className="text-[#0F172A]">{selectedTicket.created_by}</span></div>
                    <div className="flex justify-between"><span className="text-[#64748B]">Department:</span><span className="text-[#0F172A]">IT Infrastructure</span></div>
                    <div className="flex justify-between"><span className="text-[#64748B]">Request Type:</span><span className="text-indigo-650 inline-block"><RequestTypePill type={selectedTicket.request_type || "SERVICE_REQUEST"} /></span></div>
                  </div>
                </div>

                {/* Reason for Request & Justification */}
                <div className="space-y-1.5 flex flex-col font-bold">
                  <span className="text-[9px] text-[#64748B] block uppercase tracking-wider">Reason &amp; Business Justification</span>
                  <p className="text-xs text-[#334155] bg-white border border-[#E2E8F0] p-3 rounded-xl leading-normal font-semibold">
                    {selectedTicket.description || selectedTicket.issue_description}
                  </p>
                </div>

                {/* AI Recommendation */}
                <div className="space-y-1.5 bg-indigo-50 border border-indigo-200 p-4 rounded-xl flex flex-col font-bold">
                  <span className="text-[9px] text-indigo-700 block uppercase tracking-wider flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-indigo-600" aria-hidden />
                    AI Recommendation &amp; Policy Analysis
                  </span>
                  <p className="text-xs text-indigo-950 leading-normal font-semibold">
                    {selectedTicket.ai_recommendation || "Validated request parameters. Category belongs to standard entitlement guidelines."}
                  </p>
                </div>

                {/* Knowledge Used */}
                <div className="space-y-1.5 flex flex-col font-bold uppercase">
                  <span className="text-[9px] text-[#64748B] block tracking-wider">Knowledge Base Entitlements</span>
                  <div className="flex items-center gap-2 p-2.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-xs">
                    <Shield className="w-4 h-4 text-emerald-600" />
                    <span className="text-[#475569]">KB00492 - Software Provisioning Guidelines</span>
                  </div>
                </div>

                {/* Attachments */}
                <div className="space-y-1.5 flex flex-col font-bold uppercase">
                  <span className="text-[9px] text-[#64748B] block tracking-wider">Attachments</span>
                  <div className="flex items-center gap-2 p-2 bg-white border border-[#E2E8F0] rounded-xl text-xs text-indigo-650 cursor-pointer hover:bg-[#F8FAFC]">
                    <Paperclip className="w-3.5 h-3.5 text-[#94A3B8]" />
                    <span>entitlement_proof_log.pdf</span>
                  </div>
                </div>

                {/* Approval Comments Box */}
                {selectedTicket.approval_status === "PENDING" && (
                  <div className="space-y-2 pt-2 border-t border-[#E2E8F0] font-bold uppercase">
                    <label className="text-[9px] text-[#64748B] block tracking-wider">Approval / Rejection Comment</label>
                    <textarea
                      value={actionReason}
                      onChange={e => setActionReason(e.target.value)}
                      placeholder="Comment is optional for approvals, but MANDATORY for rejections..."
                      rows={3}
                      className="w-full px-3 py-2 bg-white border border-[#E2E8F0] rounded-xl text-xs font-semibold outline-none focus:ring-2 focus:ring-[#E30613]/10 focus:border-[#E30613] resize-none text-[#1E293B] normal-case"
                    />
                    <div className="flex gap-3">
                      <button
                        onClick={handleApprove}
                        disabled={actionLoading}
                        className="flex-1 py-2.5 bg-[#16A34A] hover:bg-green-700 text-white rounded-xl text-xs transition cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                        Approve Request
                      </button>
                      <button
                        onClick={handleReject}
                        disabled={actionLoading}
                        className="flex-1 py-2.5 bg-[#DC2626] hover:bg-red-700 text-white rounded-xl text-xs transition cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
                      >
                        {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                        Reject Request
                      </button>
                    </div>
                  </div>
                )}

                {/* Discussions Board */}
                <div className="space-y-3 pt-3 border-t border-[#E2E8F0] flex flex-col font-bold uppercase">
                  <span className="text-[9px] text-[#64748B] block tracking-wider">Comments &amp; Work notes</span>
                  
                  {commentsLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 text-[#94A3B8] animate-spin" />
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {comments.length === 0 ? (
                        <p className="text-[11px] text-[#64748B] italic text-center py-2 normal-case font-semibold">No comments posted yet.</p>
                      ) : (
                        comments.map((c, i) => (
                          <div key={i} className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl space-y-1 text-[11px] normal-case">
                            <div className="flex justify-between font-bold text-[#475569]">
                              <span className="uppercase tracking-wider">{c.author}</span>
                              <span className="text-[#94A3B8] font-medium">{new Date(c.created_at).toLocaleTimeString()}</span>
                            </div>
                            <p className="text-[#334155] leading-normal font-semibold">{c.text}</p>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  <div className="flex gap-2 normal-case">
                    <input
                      type="text"
                      value={newComment}
                      onChange={e => setNewComment(e.target.value)}
                      placeholder="Type a message or comment..."
                      className="flex-1 bg-white border border-[#E2E8F0] rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus:ring-1 focus:ring-[#E30613] text-[#1E293B]"
                      onKeyDown={e => { if (e.key === "Enter") handlePostComment(); }}
                    />
                    <button
                      onClick={handlePostComment}
                      disabled={!newComment.trim()}
                      className="p-2 bg-[#E30613] hover:bg-red-755 text-white rounded-xl disabled:opacity-50 transition cursor-pointer flex items-center justify-center"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Timeline */}
                <div className="space-y-3 pt-3 border-t border-[#E2E8F0]">
                  <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Ticket Timeline</span>
                  {timelineLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 text-[#94A3B8] animate-spin" />
                    </div>
                  ) : (
                    <div className="relative border-l border-[#CBD5E1] ml-2 pl-4 space-y-3 pb-2 text-[11px] font-bold">
                      {timeline.map((evt, idx) => (
                        <div key={idx} className="relative">
                          <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-white border-2 border-indigo-400" />
                          <div className="text-[9px] text-[#94A3B8] font-semibold">{new Date(evt.created_at).toLocaleString()}</div>
                          <span className="text-[#1E293B] block uppercase text-[10px] tracking-wider mt-0.5">{evt.action.replace(/_/g, " ")}</span>
                          <span className="text-[#475569] leading-relaxed block mt-0.5 normal-case font-semibold">{evt.description}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </div>
            </div>
          )}

        </div>
      </main>

      {/* Unified Ticket Details Modal for Manager */}
      <TicketDetailsModal
        isOpen={Boolean(selectedTicket)}
        onClose={() => setSelectedTicket(null)}
        ticketId={selectedTicket?.ticket_id || null}
        userRole="MANAGER"
        currentUsername={user?.username || "manager"}
        token={token}
        onTicketUpdated={() => fetchTickets(true)}
      />

    </div>
  );
}
