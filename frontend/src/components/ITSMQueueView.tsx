/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/set-state-in-effect, react-hooks/exhaustive-deps, @typescript-eslint/no-unused-vars */
"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Sparkles, Clock, CheckCircle2, XCircle, History, User, Users,
  LayoutDashboard, Search, Filter, FileText, ChevronRight,
  Check, X, ShieldAlert, Send, Loader2, Download, ChevronLeft,
  ChevronRight as ChevronRightIcon, Paperclip, Shield, Terminal,
  Settings, Activity, AlertTriangle, BookOpen, Trash2, Edit,
  Plus, RefreshCw, Upload, Database, Cpu, HelpCircle, HardDrive, CheckCheck,
  AlertCircle
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Cell, Legend, LineChart, Line
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

// ─────────────────────────────────────────────────────────────────────────────
// Interfaces
// ─────────────────────────────────────────────────────────────────────────────
interface Ticket {
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
  request_type?: string;
  manager?: string;
  approval_status?: string;
  assignment_group?: string;
  sla_hours?: number;
  sla_state?: string;
  sla_breached?: boolean;
}

interface Comment {
  id: number;
  author: string;
  text: string;
  created_at: string;
  is_internal: boolean;
}

interface TimelineEvent {
  timestamp: string;
  title: string;
  description: string;
  type: string;
  user?: string;
  role?: string;
  action?: string;
}

interface KbArticle {
  article_id: string;
  title: string;
  category: string;
  steps: string[];
  status: string;
  created_by?: string;
  created_at?: string;
  version?: number;
  screenshots?: string[];
}

interface AdUser {
  id: string;
  displayName: string;
  mail: string;
  userPrincipalName: string;
  jobTitle: string;
  department: string;
  location?: string;
}

interface ITSMQueueViewProps {
  user: any;
  token: string | null;
}

type SubView = "dashboard" | "queue" | "assigned" | "kb" | "employees" | "analytics" | "health" | "settings";

const CHART_COLORS = ["#E30613", "#2563EB", "#06B6D4", "#16A34A", "#F59E0B", "#7C3AED", "#EC4899"];

export default function ITSMQueueView({ user, token }: ITSMQueueViewProps) {
  // SubView Navigation
  const [subView, setSubView] = useState<SubView>("dashboard");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Core Data States
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [kbArticles, setKbArticles] = useState<KbArticle[]>([]);
  const [employees, setEmployees] = useState<AdUser[]>([]);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [analyticsOverview, setAnalyticsOverview] = useState<any>(null);

  // Loading States
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Selected Ticket Detail States (Drawer)
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [isInternalComment, setIsInternalComment] = useState(false);

  // Quick Action States
  const [actionLoading, setActionLoading] = useState(false);
  const [actionNote, setActionNote] = useState("");
  const [actionTeam, setActionTeam] = useState("");
  const [actionEngineer, setActionEngineer] = useState("");
  const [actionPriority, setActionPriority] = useState("");
  const [actionStatus, setActionStatus] = useState("");

  // Filters & Search Queries
  const [ticketSearch, setTicketSearch] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [categoryFilter, setCategoryFilter] = useState("ALL");

  // KB Editor State
  const [editingArticle, setEditingArticle] = useState<KbArticle | null>(null);
  const [kbSearch, setKbSearch] = useState("");
  const [uploadLoading, setUploadLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Pagination (Ticket Queue)
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  // Notification Toast
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  // Helper auth headers
  const getAuthHeaders = useCallback(() => ({
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  }), [token]);

  // Fetch standard data dependencies
  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);

    try {
      // 1. Fetch tickets
      const resTickets = await apiFetch("/tickets", { headers: getAuthHeaders() });
      if (resTickets.ok) {
        const data = await resTickets.json();
        setTickets(data || []);
      }

      // 2. Fetch KB Articles
      const resKb = await apiFetch("/api/admin/knowledge/articles", { headers: getAuthHeaders() });
      if (resKb.ok) {
        const data = await resKb.json();
        setKbArticles(data || []);
      }

      // 3. Fetch Entra ID Employees list
      const resEmp = await apiFetch("/entra/users", { headers: getAuthHeaders() });
      if (resEmp.ok) {
        const data = await resEmp.json();
        setEmployees(data || []);
      }

      // 4. Fetch System Health Status
      const resHealth = await apiFetch("/system-status", { headers: getAuthHeaders() });
      if (resHealth.ok) {
        const data = await resHealth.json();
        setHealthStatus(data || null);
      }

      // 5. Fetch Analytics overview metrics
      const resAnalytics = await apiFetch("/api/analytics/overview", { headers: getAuthHeaders() });
      if (resAnalytics.ok) {
        const data = await resAnalytics.json();
        setAnalyticsOverview(data || null);
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Error pulling data from server", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [getAuthHeaders]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch details for a specific ticket when selected
  const fetchTicketDetails = async (ticketId: string) => {
    setDetailLoading(true);
    try {
      const res = await apiFetch(`/tickets/${ticketId}/details`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setComments(data.comments || []);
        const mergedComments = [
          ...(data.comments || []).map((c: any) => ({ ...c, is_internal: false })),
          ...(data.internal_notes || []).map((c: any) => ({ ...c, is_internal: true }))
        ].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        setComments(mergedComments);
        setTimeline(data.timeline || []);
      } else {
        showToast("Failed to fetch ticket details", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network failure loading ticket details", "error");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleTicketSelect = (ticket: Ticket) => {
    setSelectedTicket(ticket);
    setActionNote("");
    setActionTeam(ticket.assigned_team || "");
    setActionEngineer(ticket.assigned_engineer || "");
    setActionPriority(ticket.priority || "");
    setActionStatus(ticket.status || "");
    fetchTicketDetails(ticket.ticket_id);
  };

  // Perform a ticket lifecycle action
  const handleTicketAction = async (action: string, overridePayload: any = {}) => {
    if (!selectedTicket) return;
    setActionLoading(true);
    try {
      const payload = {
        action,
        note: actionNote.trim() || undefined,
        team: actionTeam || undefined,
        engineer: actionEngineer || undefined,
        priority: actionPriority || undefined,
        ...overridePayload
      };

      const res = await apiFetch(`/tickets/${selectedTicket.ticket_id}/action`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || `✓ Action '${action}' run successfully`, "success");
        fetchTicketDetails(selectedTicket.ticket_id);
        fetchData(true);
        setActionNote("");
        const updated = tickets.find(t => t.ticket_id === selectedTicket.ticket_id);
        if (updated) setSelectedTicket({ ...selectedTicket, ...updated, status: data.status || selectedTicket.status });
      } else {
        showToast(data.detail || "Action failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network error submitting action", "error");
    } finally {
      setActionLoading(false);
    }
  };

  // Post comment or internal note
  const handlePostComment = async () => {
    if (!selectedTicket || !commentText.trim()) return;
    try {
      const res = await apiFetch(`/tickets/${selectedTicket.ticket_id}/comments`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          text: commentText,
          is_internal: isInternalComment
        })
      });
      if (res.ok) {
        setCommentText("");
        showToast(isInternalComment ? "Work note added" : "Reply sent to employee", "success");
        fetchTicketDetails(selectedTicket.ticket_id);
      } else {
        showToast("Failed to post comment", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Error posting message", "error");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // Computed Metrics (Dashboard)
  // ─────────────────────────────────────────────────────────────────────────────
  const dashboardStats = useMemo(() => {
    let newCount = 0;
    let assignedCount = 0;
    let inProgressCount = 0;
    let pendingCount = 0;
    let resolvedTodayCount = 0;
    let closedTodayCount = 0;

    const todayStr = new Date().toISOString().split("T")[0];

    tickets.forEach(t => {
      const status = (t.status || "").toUpperCase();
      if (status === "NEW") newCount++;
      else if (status === "ASSIGNED") assignedCount++;
      else if (status === "IN_PROGRESS") inProgressCount++;
      else if (status === "PENDING" || status === "WAITING" || status === "WAITING_FOR_USER") pendingCount++;

      if ((status === "RESOLVED" || status === "FULFILLED") && t.resolved_at) {
        if (t.resolved_at.split("T")[0] === todayStr) resolvedTodayCount++;
      }
      if (status === "CLOSED" && t.closed_at) {
        if (t.closed_at.split("T")[0] === todayStr) closedTodayCount++;
      }
    });

    const aiResRate = analyticsOverview?.overview_metrics?.ai_resolution_rate_pct
      || analyticsOverview?.ai_resolution_rate_pct
      || 72.4;

    const avgResolutionTime = analyticsOverview?.overview_metrics?.avg_resolution_time_hours
      || analyticsOverview?.avg_resolution_time_hours
      || "2.8 hrs";

    return {
      newCount,
      assignedCount,
      inProgressCount,
      pendingCount,
      resolvedToday: resolvedTodayCount,
      closedToday: closedTodayCount,
      aiResolutionRate: `${aiResRate}%`,
      avgResolutionTime: typeof avgResolutionTime === "number" ? `${avgResolutionTime} hrs` : avgResolutionTime
    };
  }, [tickets, analyticsOverview]);

  // Categories Chart
  const categoryChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    tickets.forEach(t => {
      const cat = t.category || "General";
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [tickets]);

  // Teams Chart
  const teamChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    tickets.forEach(t => {
      const team = t.assigned_team || "Helpdesk";
      counts[team] = (counts[team] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [tickets]);

  // Priority Chart
  const priorityChartData = useMemo(() => {
    const counts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
    tickets.forEach(t => {
      const p = (t.priority || "MEDIUM").toUpperCase();
      if (p in counts) counts[p]++;
    });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [tickets]);

  // Filters logic
  const filteredTickets = useMemo(() => {
    return tickets.filter(t => {
      const query = ticketSearch.toLowerCase();
      const matchesSearch = !query ||
        t.ticket_id.toLowerCase().includes(query) ||
        t.category.toLowerCase().includes(query) ||
        t.created_by.toLowerCase().includes(query) ||
        (t.description || "").toLowerCase().includes(query);

      const matchesPriority = priorityFilter === "ALL" || (t.priority || "MEDIUM").toUpperCase() === priorityFilter;
      const matchesTeam = teamFilter === "ALL" || (t.assigned_team || "Helpdesk").toUpperCase() === teamFilter.toUpperCase();
      const matchesStatus = statusFilter === "ALL" || (t.status || "NEW").toUpperCase() === statusFilter;
      const matchesCategory = categoryFilter === "ALL" || (t.category || "General").toUpperCase() === categoryFilter.toUpperCase();

      let matchesView = true;
      if (subView === "assigned") {
        matchesView = t.assigned_engineer === user.username;
      }

      return matchesSearch && matchesPriority && matchesTeam && matchesStatus && matchesCategory && matchesView;
    });
  }, [tickets, ticketSearch, priorityFilter, teamFilter, statusFilter, categoryFilter, subView, user]);

  // Paginated List
  const paginatedTickets = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredTickets.slice(start, start + itemsPerPage);
  }, [filteredTickets, currentPage]);

  const totalPages = Math.ceil(filteredTickets.length / itemsPerPage) || 1;

  useEffect(() => {
    setCurrentPage(1);
  }, [ticketSearch, priorityFilter, teamFilter, statusFilter, categoryFilter, subView]);

  // KB filtering
  const filteredKb = useMemo(() => {
    return kbArticles.filter(art => {
      const query = kbSearch.toLowerCase();
      return !query ||
        art.article_id.toLowerCase().includes(query) ||
        art.title.toLowerCase().includes(query) ||
        art.category.toLowerCase().includes(query) ||
        (art.steps || []).some(s => s.toLowerCase().includes(query));
    });
  }, [kbArticles, kbSearch]);

  // KB save handler
  const handleSaveArticle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingArticle) return;
    const isNew = !editingArticle.article_id;
    const url = isNew 
      ? "/api/admin/knowledge/articles" 
      : `/api/admin/knowledge/articles/${editingArticle.article_id}`;
    const method = isNew ? "POST" : "PUT";

    try {
      const res = await apiFetch(url, {
        method,
        headers: getAuthHeaders(),
        body: JSON.stringify(editingArticle)
      });
      if (res.ok) {
        showToast(isNew ? "Article drafted successfully" : "Article updated successfully", "success");
        setEditingArticle(null);
        fetchData(true);
      } else {
        const errData = await res.json();
        showToast(errData.detail || "Failed to save article", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network failure saving article", "error");
    }
  };

  const handlePublishArticle = async (id: string) => {
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${id}/publish`, {
        method: "POST",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        showToast("Article published successfully", "success");
        fetchData(true);
      } else {
        showToast("Publish action failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    }
  };

  const handleArchiveArticle = async (id: string) => {
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${id}/archive`, {
        method: "POST",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        showToast("Article archived", "success");
        fetchData(true);
      } else {
        showToast("Archive action failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    }
  };

  const handleDeleteArticle = async (id: string) => {
    if (!confirm("Are you sure you want to delete this article?")) return;
    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        showToast("Article deleted", "success");
        fetchData(true);
      } else {
        showToast("Delete action failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
    }
  };

  const handleScreenshotUpload = async (articleId: string, file: File) => {
    setUploadLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiFetch(`/api/admin/knowledge/articles/${articleId}/upload`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData
      });
      if (res.ok) {
        showToast("Screenshot uploaded successfully", "success");
        fetchData(true);
      } else {
        showToast("Screenshot upload failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network error uploading image", "error");
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="flex h-full w-full bg-[#F8FAFC] font-sans overflow-hidden">

      {/* Toast notifications */}
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
        className={`fixed inset-y-0 left-0 z-40 w-60 bg-white border-r border-[#E2E8F0] flex flex-col pt-3 pb-4 shadow-xl transform transition-transform duration-300 ease-in-out md:hidden ${isSidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
      >
        <div className="flex items-center justify-between px-4 pb-3 border-b border-[#F1F5F9] mb-2">
          <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-wider">Console Navigation</span>
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
            { id: "queue", label: "Ticket Queue", icon: <Terminal className="w-4 h-4" />, badge: tickets.filter(t => t.status === "NEW").length },
            { id: "assigned", label: "Assigned Tickets", icon: <User className="w-4 h-4" />, badge: tickets.filter(t => t.assigned_engineer === user.username && t.status !== "CLOSED").length },
            { id: "kb", label: "Knowledge Base", icon: <BookOpen className="w-4 h-4" /> },
            { id: "employees", label: "Employees Portal", icon: <Users className="w-4 h-4" /> },
            { id: "analytics", label: "ITSM Analytics", icon: <Activity className="w-4 h-4" /> },
            { id: "health", label: "System Health", icon: <Cpu className="w-4 h-4" /> },
            { id: "settings", label: "Console Settings", icon: <Settings className="w-4 h-4" /> },
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

      {/* INTERNAL CONSOLE SIDEBAR (DESKTOP) */}
      <aside className="w-60 bg-white border-r border-[#E2E8F0] hidden md:flex flex-col flex-shrink-0">
        <nav className="flex-1 px-3 py-4 space-y-1">
          {[
            { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-4 h-4" /> },
            { id: "queue", label: "Ticket Queue", icon: <Terminal className="w-4 h-4" />, badge: tickets.filter(t => t.status === "NEW").length },
            { id: "assigned", label: "Assigned Tickets", icon: <User className="w-4 h-4" />, badge: tickets.filter(t => t.assigned_engineer === user.username && t.status !== "CLOSED").length },
            { id: "kb", label: "Knowledge Base", icon: <BookOpen className="w-4 h-4" /> },
            { id: "employees", label: "Employees Portal", icon: <Users className="w-4 h-4" /> },
            { id: "analytics", label: "ITSM Analytics", icon: <Activity className="w-4 h-4" /> },
            { id: "health", label: "System Health", icon: <Cpu className="w-4 h-4" /> },
            { id: "settings", label: "Console Settings", icon: <Settings className="w-4 h-4" /> },
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
              A
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-[#0F172A] block truncate">
                {user?.username ? user.username.charAt(0).toUpperCase() + user.username.slice(1) : "Administrator"}
              </span>
              <span className="text-[9px] text-[#64748B] font-semibold block uppercase">
                {user?.role || "ADMIN"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN VIEW AREA */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        <header className="h-12 bg-white border-b border-[#E2E8F0] flex items-center justify-between px-6 flex-shrink-0 z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
              title="Open console menu"
              aria-label="Open console menu"
            >
              <Filter className="w-3.5 h-3.5" />
            </button>
            <h2 className="text-xs font-black text-[#0F172A] uppercase tracking-wider">
              Admin Console: {subView.replace(/_/g, " ")}
            </h2>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="p-1.5 rounded-lg border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] cursor-pointer disabled:opacity-50"
              title="Refresh Queue"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-6 min-h-0 flex flex-col lg:flex-row gap-6 relative">
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 text-[#E30613] animate-spin" />
              <span className="text-xs font-bold text-[#64748B]">Loading console interface...</span>
            </div>
          ) : (
            <div className="flex-1 min-w-0 space-y-6">

              {/* DASHBOARD VIEW */}
              {subView === "dashboard" && (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { label: "New Tickets", value: dashboardStats.newCount, icon: <HelpCircle className="w-4 h-4 text-blue-600" /> },
                      { label: "Assigned Queue", value: dashboardStats.assignedCount, icon: <User className="w-4 h-4 text-indigo-600" /> },
                      { label: "In Progress", value: dashboardStats.inProgressCount, icon: <Loader2 className="w-4 h-4 text-amber-600" /> },
                      { label: "Pending Today", value: dashboardStats.pendingCount, icon: <Clock className="w-4 h-4 text-orange-655" /> },
                      { label: "Resolved Today", value: dashboardStats.resolvedToday, icon: <CheckCircle2 className="w-4 h-4 text-green-600" /> },
                      { label: "Closed Today", value: dashboardStats.closedToday, icon: <CheckCheck className="w-4 h-4 text-slate-600" /> },
                      { label: "AI Resolution Rate", value: dashboardStats.aiResolutionRate, icon: <Sparkles className="w-4 h-4 text-purple-600" /> },
                      { label: "Avg Resolution Time", value: dashboardStats.avgResolutionTime, icon: <Activity className="w-4 h-4 text-red-600" /> },
                    ].map((card, i) => (
                      <div key={i} className="bg-white p-4 border border-[#E2E8F0] rounded-2xl flex items-center justify-between shadow-xs">
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider block">{card.label}</span>
                          <span className="text-lg font-bold text-[#0F172A] block">{card.value}</span>
                        </div>
                        <div className="w-8 h-8 rounded-xl bg-[#F8FAFC] flex items-center justify-center border border-[#E2E8F0]">
                          {card.icon}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Tickets by Category</span>
                      <div className="h-60 w-full flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie data={categoryChartData} cx="50%" cy="50%" innerRadius={50} outerRadius={70} paddingAngle={2} dataKey="value">
                              {categoryChartData.map((e, index) => <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}
                            </Pie>
                            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                            <Legend wrapperStyle={{ fontSize: 10 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Tickets by Team</span>
                      <div className="h-60 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={teamChartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                            <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                            <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                            <Bar dataKey="value" fill="#E30613" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Priority Levels</span>
                      <div className="h-60 w-full flex items-center justify-center">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie data={priorityChartData} cx="50%" cy="50%" innerRadius={50} outerRadius={70} paddingAngle={3} dataKey="value">
                              {priorityChartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.name === "CRITICAL" ? "#EF4444" : entry.name === "HIGH" ? "#F97316" : entry.name === "MEDIUM" ? "#EAB308" : "#22C55E"} />
                              ))}
                            </Pie>
                            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                            <Legend wrapperStyle={{ fontSize: 10 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TICKET QUEUE VIEW / ASSIGNED TICKETS */}
              {(subView === "queue" || subView === "assigned") && (
                <div className="space-y-4">
                  <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
                    <div className="w-64">
                      <SearchInput
                        value={ticketSearch}
                        onChange={e => setTicketSearch(e.target.value)}
                        placeholder="Search requester, issue..."
                      />
                    </div>

                    <div className="flex flex-wrap gap-2 w-full sm:w-auto">
                      <select
                        value={priorityFilter}
                        onChange={e => setPriorityFilter(e.target.value)}
                        className="px-3 py-1.5 text-xs rounded-xl border border-[#E2E8F0] bg-white outline-none focus:border-[#E30613] font-bold text-[#475569]"
                      >
                        <option value="ALL">All Priorities</option>
                        <option value="LOW">Low</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HIGH">High</option>
                        <option value="CRITICAL">Critical</option>
                      </select>

                      <select
                        value={teamFilter}
                        onChange={e => setTeamFilter(e.target.value)}
                        className="px-3 py-1.5 text-xs rounded-xl border border-[#E2E8F0] bg-white outline-none focus:border-[#E30613] font-bold text-[#475569]"
                      >
                        <option value="ALL">All Teams</option>
                        <option value="Helpdesk">Helpdesk</option>
                        <option value="Network">Network</option>
                        <option value="Sysadmin">Sysadmin</option>
                        <option value="Security">Security</option>
                      </select>

                      <select
                        value={statusFilter}
                        onChange={e => setStatusFilter(e.target.value)}
                        className="px-3 py-1.5 text-xs rounded-xl border border-[#E2E8F0] bg-white outline-none focus:border-[#E30613] font-bold text-[#475569]"
                      >
                        <option value="ALL">All Statuses</option>
                        <option value="NEW">New</option>
                        <option value="ASSIGNED">Assigned</option>
                        <option value="IN_PROGRESS">In Progress</option>
                        <option value="PENDING">Pending</option>
                        <option value="RESOLVED">Resolved</option>
                        <option value="CLOSED">Closed</option>
                      </select>
                    </div>
                  </div>

                  {paginatedTickets.length === 0 ? (
                    <div className="bg-white border border-[#E2E8F0] rounded-xl p-12 text-center text-[#94A3B8] italic font-semibold">
                      No tickets in the queue matching filters.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {["Ticket ID", "Requester", "Team Assigned", "Priority", "Category", "Created", "SLA Info", "Status", ""].map(h => (
                            <TableHead key={h}>{h}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedTickets.map(t => (
                          <TableRow key={t.ticket_id}>
                            <TableCell className="font-mono font-bold text-[#1E293B]">{t.ticket_id}</TableCell>
                            <TableCell className="font-semibold text-[#1E293B]">{t.created_by}</TableCell>
                            <TableCell className="font-semibold text-[#475569]">{t.assigned_team || "Helpdesk"}</TableCell>
                            <TableCell>
                              <PriorityPill priority={t.priority || "MEDIUM"} />
                            </TableCell>
                            <TableCell className="text-[#475569]">{t.category}</TableCell>
                            <TableCell className="text-[#64748B]">{new Date(t.created_at).toLocaleDateString()}</TableCell>
                            <TableCell className="font-semibold">
                              <span className={t.sla_breached ? "text-[#E30613]" : "text-[#16A34A]"}>
                                {t.sla_breached ? "BREACHED" : `${t.sla_hours || 4}h Limit`}
                              </span>
                            </TableCell>
                            <TableCell>
                              <StatusPill status={t.status} />
                            </TableCell>
                            <TableCell className="text-right">
                              <button
                                onClick={() => handleTicketSelect(t)}
                                className="px-2.5 py-1 text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl font-bold text-[10.5px] cursor-pointer border border-[#E2E8F0] shadow-xs"
                              >
                                Console
                              </button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}

                  {/* Pagination Footer */}
                  {filteredTickets.length > itemsPerPage && (
                    <div className="p-4 border border-[#E2E8F0] rounded-xl bg-white flex items-center justify-between">
                      <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">
                        Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, filteredTickets.length)} of {filteredTickets.length}
                      </span>
                      <div className="flex gap-2">
                        <button
                          disabled={currentPage === 1}
                          onClick={() => setCurrentPage(c => Math.max(c - 1, 1))}
                          className="p-1.5 border border-[#E2E8F0] rounded-xl disabled:opacity-40 cursor-pointer hover:bg-[#F8FAFC]"
                        >
                          <ChevronLeft className="w-3.5 h-3.5 text-[#475569]" />
                        </button>
                        <button
                          disabled={currentPage === totalPages}
                          onClick={() => setCurrentPage(c => Math.min(c + 1, totalPages))}
                          className="p-1.5 border border-[#E2E8F0] rounded-xl disabled:opacity-40 cursor-pointer hover:bg-[#F8FAFC]"
                        >
                          <ChevronRightIcon className="w-3.5 h-3.5 text-[#475569]" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* KNOWLEDGE BASE MANAGEMENT VIEW */}
              {subView === "kb" && (
                <div className="space-y-6">
                  {editingArticle ? (
                    <form onSubmit={handleSaveArticle} className="bg-white p-6 border border-[#E2E8F0] rounded-2xl space-y-4 font-bold">
                      <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">
                        {editingArticle.article_id ? "Edit KB Article" : "Create New KB Article"}
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Article ID (e.g. KB00100)</label>
                          <input
                            type="text"
                            value={editingArticle.article_id}
                            disabled={!!editingArticle.article_id}
                            onChange={e => setEditingArticle({ ...editingArticle, article_id: e.target.value })}
                            className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs font-semibold text-[#1E293B]"
                            required
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Category</label>
                          <input
                            type="text"
                            value={editingArticle.category}
                            onChange={e => setEditingArticle({ ...editingArticle, category: e.target.value })}
                            className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs font-semibold text-[#1E293B]"
                            required
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-[#64748B] uppercase">Title</label>
                        <input
                          type="text"
                          value={editingArticle.title}
                          onChange={e => setEditingArticle({ ...editingArticle, title: e.target.value })}
                          className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs font-semibold text-[#1E293B]"
                          required
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-[#64748B] uppercase">Troubleshooting Steps (separated by newlines)</label>
                        <textarea
                          value={editingArticle.steps.join("\n")}
                          onChange={e => setEditingArticle({ ...editingArticle, steps: e.target.value.split("\n") })}
                          className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs font-semibold text-[#1E293B] focus:ring-1 focus:ring-[#E30613] outline-none"
                          rows={6}
                          required
                        />
                      </div>

                      <div className="flex justify-end gap-3 pt-2">
                        <button
                          type="button"
                          onClick={() => setEditingArticle(null)}
                          className="px-4 py-2 text-xs font-bold border border-[#E2E8F0] rounded-xl hover:bg-[#F8FAFC] cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="px-4 py-2 text-xs font-bold text-white bg-[#E30613] hover:bg-red-700 rounded-xl cursor-pointer"
                        >
                          Save Draft
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="w-64">
                          <SearchInput
                            value={kbSearch}
                            onChange={e => setKbSearch(e.target.value)}
                            placeholder="Search Knowledge Base..."
                          />
                        </div>

                        <button
                          onClick={() => setEditingArticle({ article_id: "", title: "", category: "", steps: [], status: "DRAFT" })}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold text-xs rounded-xl cursor-pointer shadow-xs"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          New Article
                        </button>
                      </div>

                      <Table>
                        <TableHeader>
                          <TableRow>
                            {["Article ID", "Title", "Category", "Status", "Steps count", ""].map(h => (
                              <TableHead key={h}>{h}</TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {filteredKb.map(art => (
                            <TableRow key={art.article_id}>
                              <TableCell className="font-mono font-bold text-[#1E293B]">{art.article_id}</TableCell>
                              <TableCell className="font-semibold text-[#1E293B]">{art.title}</TableCell>
                              <TableCell className="text-[#475569]">{art.category}</TableCell>
                              <TableCell>
                                <StatusPill status={art.status} />
                              </TableCell>
                              <TableCell className="text-[#64748B]">{(art.steps || []).length} steps</TableCell>
                              <TableCell className="text-right flex items-center justify-end gap-2.5">
                                <button
                                  onClick={() => setEditingArticle(art)}
                                  className="p-1 hover:bg-[#F1F5F9] border border-transparent hover:border-[#E2E8F0] rounded-xl text-indigo-650 cursor-pointer transition-all"
                                  title="Edit Article"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                </button>
                                {art.status !== "PUBLISHED" && (
                                  <button
                                    onClick={() => handlePublishArticle(art.article_id)}
                                    className="text-[10px] font-bold text-[#16A34A] hover:underline cursor-pointer"
                                  >
                                    Publish
                                  </button>
                                )}
                                {art.status === "PUBLISHED" && (
                                  <button
                                    onClick={() => handleArchiveArticle(art.article_id)}
                                    className="text-[10px] font-bold text-orange-600 hover:underline cursor-pointer"
                                  >
                                    Archive
                                  </button>
                                )}
                                <button
                                  onClick={() => handleDeleteArticle(art.article_id)}
                                  className="p-1 hover:bg-[#F1F5F9] border border-transparent hover:border-[#E2E8F0] rounded-xl text-[#E30613] cursor-pointer transition-all"
                                  title="Delete"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                                <div className="relative">
                                  <input
                                    type="file"
                                    accept="image/*"
                                    className="hidden"
                                    id={`upload-${art.article_id}`}
                                    onChange={e => {
                                      const file = e.target.files?.[0];
                                      if (file) handleScreenshotUpload(art.article_id, file);
                                    }}
                                  />
                                  <label
                                    htmlFor={`upload-${art.article_id}`}
                                    className="p-1 hover:bg-[#F1F5F9] border border-transparent hover:border-[#E2E8F0] rounded-xl text-indigo-650 cursor-pointer flex items-center transition-all"
                                    title="Upload Screenshot"
                                  >
                                    <Upload className="w-3.5 h-3.5" />
                                  </label>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              )}

              {/* EMPLOYEES VIEW */}
              {subView === "employees" && (
                <div className="space-y-2">
                  <div className="bg-white border border-[#E2E8F0] p-4 rounded-xl">
                    <span className="text-[10px] font-black text-[#0F172A] block uppercase mb-1">Enterprise Employee Directory</span>
                    <p className="text-[10.5px] text-[#64748B] font-bold uppercase tracking-wider mt-1">Reflecting live synchronized details from Active Directory / Entra ID identity provider gateway.</p>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        {["DisplayName", "Email Address", "UserPrincipalName", "Job Title", "Department", "Linked workstation"].map(h => (
                          <TableHead key={h}>{h}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {employees.map((emp, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-semibold text-[#1E293B]">{emp.displayName}</TableCell>
                          <TableCell className="font-mono text-[#334155]">{emp.mail || `${emp.userPrincipalName}@bridgestone.com`}</TableCell>
                          <TableCell className="text-[#475569] font-semibold">{emp.userPrincipalName}</TableCell>
                          <TableCell className="text-[#475569]">{emp.jobTitle}</TableCell>
                          <TableCell className="text-[#475569]">{emp.department}</TableCell>
                          <TableCell className="font-mono text-[#64748B]">{emp.userPrincipalName === "admin" ? "BS-ADM-SRV3" : emp.userPrincipalName === "manager" ? "BS-MGR-LAP8" : "BS-EMP-WS09"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* ANALYTICS VIEW */}
              {subView === "analytics" && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">SLA Compliance Rate (Active)</span>
                      <div className="h-60 w-full flex flex-col justify-between">
                        <div className="text-2xl font-bold text-[#16A34A] block mt-2">
                          {analyticsOverview?.overview_metrics?.sla_compliance_pct || "98.2"}%
                        </div>
                        <span className="text-[10px] text-[#64748B] block font-bold uppercase mt-1">IT Service Desk Compliance Target: 95.0%</span>
                        <div className="h-40 w-full mt-4">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={[
                              { name: "Day 1", pct: 94 },
                              { name: "Day 2", pct: 96 },
                              { name: "Day 3", pct: 95.5 },
                              { name: "Day 4", pct: 98.2 },
                            ]}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                              <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                              <YAxis domain={[90, 100]} tick={{ fontSize: 9 }} stroke="#94a3b8" />
                              <Tooltip />
                              <Line type="monotone" dataKey="pct" stroke="#10B981" strokeWidth={2} dot />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs">
                      <span className="text-xs font-bold text-[#0F172A] block mb-4 uppercase tracking-wider">Volume Trend</span>
                      <div className="h-60 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={[
                            { name: "Mon", Tickets: 12 },
                            { name: "Tue", Tickets: 19 },
                            { name: "Wed", Tickets: 15 },
                            { name: "Thu", Tickets: 22 },
                            { name: "Fri", Tickets: 9 },
                          ]}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                            <XAxis dataKey="name" tick={{ fontSize: 9 }} stroke="#94a3b8" />
                            <YAxis tick={{ fontSize: 9 }} stroke="#94a3b8" />
                            <Tooltip />
                            <Bar dataKey="Tickets" fill="#E30613" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* SYSTEM HEALTH VIEW */}
              {subView === "health" && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {[
                    { name: "Enterprise AI Service", state: healthStatus?.gemini || "healthy", icon: <Sparkles className="w-4 h-4 text-purple-650" />, desc: "AI diagnosis and intent classification services." },
                    { name: "SQL Database Server", state: healthStatus?.database || "healthy", icon: <Database className="w-4 h-4 text-blue-600" />, desc: "Relational ticketing and audit schema database." },
                    { name: "Redis Memory Cache", state: healthStatus?.redis || "healthy", icon: <HardDrive className="w-4 h-4 text-orange-600" />, desc: "State machine tracking and lock buffers." },
                    { name: "ServiceNow Sync Gateway", state: healthStatus?.adapters?.ServiceNow?.status || "healthy", icon: <Terminal className="w-4 h-4 text-green-600" />, desc: "Bidirectional enterprise ticketing synchronization." },
                    { name: "Microsoft Entra ID Adapter", state: healthStatus?.adapters?.["Active Directory"]?.status || "healthy", icon: <Users className="w-4 h-4 text-indigo-600" />, desc: "Workforce directory and authentication state." },
                  ].map((healthItem, idx) => (
                    <div key={idx} className="bg-white p-5 border border-[#E2E8F0] rounded-2xl shadow-xs space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {healthItem.icon}
                          <span className="text-xs font-bold text-[#0F172A]">{healthItem.name}</span>
                        </div>
                        <StatusPill status={healthItem.state === "healthy" ? "healthy" : "unhealthy"} />
                      </div>
                      <p className="text-[10.5px] text-[#64748B] leading-normal font-semibold">{healthItem.desc}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* CONSOLE SETTINGS VIEW */}
              {subView === "settings" && (
                <div className="max-w-2xl bg-white border border-[#E2E8F0] p-6 rounded-2xl shadow-xs space-y-6">
                  <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Admin Console Configuration</h3>

                  <div className="space-y-4 text-xs font-semibold text-[#334155]">
                    <div className="flex items-center justify-between p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                      <div>
                        <span className="text-[#0F172A] font-bold block">Auto-Assign Tickets</span>
                        <span className="text-[9px] text-[#64748B] block mt-0.5">Dispatch new incidents to teams using round-robin logic.</span>
                      </div>
                      <input type="checkbox" defaultChecked className="w-4 h-4 text-[#E30613] border-gray-300 focus:ring-[#E30613]" />
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                      <div>
                        <span className="text-[#0F172A] font-bold block">Escalate SLA warnings</span>
                        <span className="text-[9px] text-[#64748B] block mt-0.5">Notify engineers when tickets reach 75% or 90% SLA countdown.</span>
                      </div>
                      <input type="checkbox" defaultChecked className="w-4 h-4 text-[#E30613] border-gray-300 focus:ring-[#E30613]" />
                    </div>

                    <div className="flex items-center justify-between p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl">
                      <div>
                        <span className="text-[#0F172A] font-bold block">Synchronize ServiceNow logs</span>
                        <span className="text-[9px] text-[#64748B] block mt-0.5">Synchronize resolving, closing, and updating actions with ServiceNow.</span>
                      </div>
                      <input type="checkbox" defaultChecked className="w-4 h-4 text-[#E30613] border-gray-300 focus:ring-[#E30613]" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* DETAIL DRAWER / OVERLAY PANEL */}
          {selectedTicket && (
            <div className="w-full lg:w-[500px] bg-white border border-[#E2E8F0] rounded-2xl flex flex-col shadow-lg overflow-hidden flex-shrink-0 z-20 h-[calc(100vh-80px)] lg:h-auto font-sans">
              <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
                <div>
                  <h3 className="font-bold text-[#0F172A] text-xs flex items-center gap-1.5 uppercase tracking-wider">
                    <FileText className="w-4 h-4 text-indigo-500" />
                    Console Actions Panel
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

              {detailLoading ? (
                <div className="flex-1 flex flex-col items-center justify-center p-6">
                  <Loader2 className="w-6 h-6 text-indigo-500 animate-spin" />
                  <span className="text-xs text-[#64748B] font-semibold mt-2">Loading ticket history details...</span>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-5 space-y-5">
                  <div className="flex flex-wrap gap-1.5">
                    <StatusPill status={selectedTicket.status} />
                    <PriorityPill priority={selectedTicket.priority || "MEDIUM"} />
                    {selectedTicket.request_type && (
                      <RequestTypePill type={selectedTicket.request_type} />
                    )}
                  </div>

                  <div className="space-y-2 bg-[#F8FAFC] border border-[#E2E8F0] p-3.5 rounded-xl">
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Employee Information</span>
                    <div className="text-xs space-y-1 text-[#334155] font-bold uppercase">
                      <div className="flex justify-between"><span className="text-[#64748B]">Name:</span><span className="text-[#0F172A]">{selectedTicket.created_by}</span></div>
                      <div className="flex justify-between"><span className="text-[#64748B]">Department:</span><span className="text-[#0F172A]">Bridgestone Corporate IT</span></div>
                    </div>
                  </div>

                  <div className="space-y-1.5 flex flex-col font-bold">
                    <span className="text-[9px] text-[#64748B] block uppercase tracking-wider">Issue Description / Symptoms</span>
                    <p className="text-xs text-[#334155] bg-white border border-[#E2E8F0] p-3 rounded-xl leading-normal font-semibold">
                      {selectedTicket.description || selectedTicket.issue_description}
                    </p>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-[#E2E8F0] font-bold uppercase">
                    <span className="text-[9px] text-[#64748B] block tracking-wider">Conversation History</span>
                    <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl space-y-3.5 max-h-56 overflow-y-auto pr-1">
                      {timeline.filter(e => e.type === "chat" || e.action === "post_comment").length === 0 ? (
                        <p className="text-[11px] text-[#64748B] italic text-center py-2 normal-case font-semibold">No preceding chatbot turns logged.</p>
                      ) : (
                        timeline.filter(e => e.type === "chat" || e.action === "post_comment").map((evt, idx) => (
                          <div key={idx} className="space-y-1 text-[11px] normal-case">
                            <div className="flex justify-between font-bold text-[#64748B]">
                              <span className="uppercase tracking-wider">{evt.user || "requester"}</span>
                              <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                            </div>
                            <p className="text-[#1E293B] leading-normal font-semibold">{evt.description}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="space-y-3 pt-2 border-t border-[#E2E8F0] flex flex-col font-bold uppercase">
                    <span className="text-[9px] text-[#64748B] block tracking-wider">Comments &amp; Work Notes</span>

                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {comments.length === 0 ? (
                        <p className="text-[11px] text-[#64748B] italic text-center py-2 normal-case font-semibold">No work notes or comments logged.</p>
                      ) : (
                        comments.map((c, i) => (
                          <div key={i} className={`p-2.5 rounded-xl border space-y-1 text-[11px] normal-case ${c.is_internal
                              ? "bg-yellow-50/50 border-yellow-200"
                              : "bg-[#F8FAFC] border-[#E2E8F0]"
                            }`}>
                            <div className="flex justify-between font-bold">
                              <span className={c.is_internal ? "text-yellow-800 flex items-center gap-1" : "text-indigo-650"}>
                                {c.is_internal && <Shield className="w-3 h-3 text-yellow-600" />}
                                {c.author} {c.is_internal ? "(Internal Note)" : "(Reply to Employee)"}
                              </span>
                              <span className="text-[#94A3B8] font-medium">{new Date(c.created_at).toLocaleTimeString()}</span>
                            </div>
                            <p className="text-[#334155] leading-normal font-semibold">{c.text}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="space-y-2 normal-case">
                      <input
                        type="text"
                        value={commentText}
                        onChange={e => setCommentText(e.target.value)}
                        placeholder="Type note or reply details..."
                        className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-1.5 text-xs font-semibold outline-none focus:ring-1 focus:ring-[#E30613] text-[#1E293B]"
                        onKeyDown={e => { if (e.key === "Enter") handlePostComment(); }}
                      />
                      <div className="flex justify-between items-center gap-2">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-[#64748B] uppercase tracking-wider">
                          <input
                            type="checkbox"
                            checked={isInternalComment}
                            onChange={e => setIsInternalComment(e.target.checked)}
                            className="w-3.5 h-3.5"
                            id="internal-check"
                          />
                          <label htmlFor="internal-check" className="cursor-pointer">Internal Work note</label>
                        </div>
                        <button
                          onClick={handlePostComment}
                          disabled={!commentText.trim()}
                          className="px-3 py-1.5 bg-[#E30613] hover:bg-red-750 text-white text-xs font-bold rounded-xl disabled:opacity-50 transition cursor-pointer flex items-center justify-center gap-1 shadow-xs"
                        >
                          <Send className="w-3.5 h-3.5" />
                          Send Note
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Actions Console controls */}
                  <div className="space-y-4 pt-4 border-t border-[#E2E8F0] font-bold uppercase">
                    <span className="text-[9px] text-[#64748B] block tracking-wider">Console Command Center</span>

                    <div className="space-y-1">
                      <label className="text-[10px] font-bold text-[#64748B] block tracking-wider">Action Justification Note</label>
                      <textarea
                        value={actionNote}
                        onChange={e => setActionNote(e.target.value)}
                        placeholder="Optional for status updates, but required for assignments or reopens..."
                        rows={2}
                        className="w-full px-3 py-2 bg-white border border-[#E2E8F0] rounded-xl text-xs font-semibold outline-none focus:ring-1 focus:ring-[#E30613] resize-none text-[#1E293B] normal-case"
                      />
                    </div>

                    {(selectedTicket.status === "WAITING_ADMIN_APPROVAL" || selectedTicket.status === "WAITING_ADMIN") && (
                      <button
                        onClick={() => handleTicketAction("admin_approve")}
                        disabled={actionLoading}
                        className="w-full py-2.5 bg-emerald-650 hover:bg-emerald-700 text-white font-bold rounded-xl transition cursor-pointer flex items-center justify-center gap-1.5 shadow-md uppercase tracking-wider text-[11px] mb-3"
                      >
                        <Shield className="w-4 h-4" />
                        Approve LAPS Access
                      </button>
                    )}

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <button
                        onClick={() => handleTicketAction("accept")}
                        disabled={actionLoading || selectedTicket.status === "ASSIGNED" || selectedTicket.status === "IN_PROGRESS"}
                        className="w-full py-2 bg-indigo-650 hover:bg-indigo-700 text-white font-bold rounded-xl transition cursor-pointer disabled:opacity-40"
                      >
                        Accept Ticket
                      </button>

                      <button
                        onClick={() => handleTicketAction("start_work")}
                        disabled={actionLoading || selectedTicket.status === "IN_PROGRESS"}
                        className="w-full py-2 bg-amber-650 hover:bg-amber-700 text-white font-bold rounded-xl transition cursor-pointer disabled:opacity-40"
                      >
                        Start Work
                      </button>
                    </div>

                    <div className="space-y-3.5 bg-[#F8FAFC] p-3 rounded-xl border border-[#E2E8F0] text-xs">
                      <span className="text-[9px] text-[#64748B] block tracking-wider">Assignment parameters</span>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <label className="text-[9px] font-bold text-[#64748B] tracking-wider">Assignment Group</label>
                          <select
                            value={actionTeam}
                            onChange={e => setActionTeam(e.target.value)}
                            className="w-full px-2 py-1.5 bg-white border border-[#E2E8F0] rounded-lg text-[#1E293B] font-bold"
                          >
                            <option value="Helpdesk">Helpdesk</option>
                            <option value="Network">Network</option>
                            <option value="Sysadmin">Sysadmin</option>
                            <option value="Security">Security</option>
                            <option value="Hardware">Hardware</option>
                          </select>
                        </div>
                        <div className="space-y-1 font-semibold">
                          <label className="text-[9px] font-bold text-[#64748B] tracking-wider">Assignee Engineer</label>
                          <input
                            type="text"
                            value={actionEngineer}
                            onChange={e => setActionEngineer(e.target.value)}
                            placeholder="Engineer name..."
                            className="w-full px-2 py-1 bg-white border border-[#E2E8F0] rounded-lg text-[#1E293B] normal-case"
                          />
                        </div>
                      </div>
                      <button
                        onClick={() => handleTicketAction("assign")}
                        disabled={actionLoading}
                        className="w-full py-1.5 bg-blue-650 hover:bg-blue-700 text-white font-bold rounded-lg transition cursor-pointer"
                      >
                        Assign Technician / Group
                      </button>
                    </div>

                    <div className="space-y-3.5 bg-[#F8FAFC] p-3 rounded-xl border border-[#E2E8F0] text-xs">
                      <span className="text-[9px] text-[#64748B] block tracking-wider">State Transitions</span>
                      <div className="grid grid-cols-3 gap-2">
                        <button
                          onClick={() => handleTicketAction("resolve")}
                          disabled={actionLoading || selectedTicket.status === "RESOLVED" || selectedTicket.status === "CLOSED"}
                          className="py-1.5 bg-[#16A34A] hover:bg-green-700 text-white font-bold rounded-lg cursor-pointer disabled:opacity-40"
                        >
                          Resolve
                        </button>

                        <button
                          onClick={() => handleTicketAction("close")}
                          disabled={actionLoading || selectedTicket.status === "CLOSED"}
                          className="py-1.5 bg-slate-700 hover:bg-slate-800 text-white font-bold rounded-lg cursor-pointer disabled:opacity-40"
                        >
                          Close
                        </button>

                        <button
                          onClick={() => handleTicketAction("reopen")}
                          disabled={actionLoading || (selectedTicket.status !== "RESOLVED" && selectedTicket.status !== "CLOSED")}
                          className="py-1.5 bg-[#E30613] hover:bg-red-700 text-white font-bold rounded-lg cursor-pointer disabled:opacity-40"
                        >
                          Reopen
                        </button>
                      </div>

                      <button
                        onClick={() => handleTicketAction("pending")}
                        disabled={actionLoading || selectedTicket.status === "PENDING"}
                        className="w-full py-1.5 bg-orange-650 hover:bg-orange-700 text-white font-bold rounded-lg cursor-pointer disabled:opacity-40"
                      >
                        Place in Pending State
                      </button>
                    </div>
                  </div>

                  <div className="space-y-3 pt-3 border-t border-[#E2E8F0]">
                    <span className="text-[9px] text-[#64748B] block font-bold uppercase tracking-wider">Ticket Event Timeline</span>
                    <div className="relative border-l border-[#CBD5E1] ml-2 pl-4 space-y-3 pb-2 text-[11px] font-bold">
                      {timeline.map((evt, idx) => (
                        <div key={idx} className="relative">
                          <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-white border-2 border-indigo-400" />
                          <div className="text-[9px] text-[#94A3B8] font-semibold">{new Date(evt.timestamp).toLocaleString()}</div>
                          <span className="text-[#1E293B] block uppercase text-[10px] tracking-wider mt-0.5">{evt.title}</span>
                          <span className="text-[#475569] leading-relaxed block mt-0.5 normal-case font-semibold">{evt.description}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      </main>
    </div>
  );
}
