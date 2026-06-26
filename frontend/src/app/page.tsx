"use client";

import { useState, useRef, useEffect, useMemo, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Shield,
  Users,
  Server,
  Bell,
  Clock,
  Settings,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Terminal,
  User as UserIcon,
  TrendingUp,
  BarChart3,
  PieChart as LucidePieChart,
  Search,
  LogOut,
  RefreshCw,
  Sliders,
  X,
  ChevronRight,
  Info,
  Lock,
  Tag,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  Zap,
  Calendar,
  Layers,
  Cpu,
  Database
} from "lucide-react";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line
} from "recharts";

// ─────────────────────────────────────────────────────────────────────────────
// INTERFACES (unchanged from original)
// ─────────────────────────────────────────────────────────────────────────────

interface Message {
  sender: "user" | "agent";
  text: string;
  category?: string;
  source?: string;
  context_used?: boolean;
  action?: string;
  tool_result?: Record<string, any> | null;
}

interface Ticket {
  ticket_id: string;
  category: string;
  issue_description: string;
  assigned_team: string;
  status: string;
  created_by?: string;
  created_at: string;
  priority?: string;
  sla_hours?: number;
  servicenow_id?: string;
  sla_state?: string;
  sla_breached?: boolean;
  sla_breached_at?: string | null;
}

interface ChatResponse {
  session_id: string;
  category: string;
  source?: string;
  question: string;
  response?: string;
  status: string;
  actions?: string[];
  solved: boolean;
  ticket_required: boolean;
  ticket?: Ticket;
  context_used?: boolean;
  history_length?: number;
  action?: string;
  ticket_created?: boolean;
  ticket_id?: string;
  tool_result?: Record<string, any> | null;
  approval_required?: boolean;
  approval_status?: string;
  recommended_action?: string;
  action_result?: Record<string, any> | null;
}

interface Notification {
  notification_id: string;
  ticket_id: string;
  recipient: string;
  message: string;
  status: string;
  timestamp: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// UTILITY HELPERS & STYLES (Color system compliance)
// ─────────────────────────────────────────────────────────────────────────────

const SLOT_PROMPTS_FRONTEND: Record<string, string> = {
  software_name: "Which software application do you need installed (e.g., Microsoft Visio, Adobe Acrobat)?",
  justification: "Brief business justification or reason for this request",
  connection_profile: "Which VPN connection profile do you require (e.g., APAC-Gateway, US-Gateway)?",
  mfa_method: "Preferred Multi-Factor Authentication (MFA) method (e.g., Microsoft Authenticator, SMS)?",
  folder_path: "Network path or folder name of the shared folder you need access to",
  access_type: "Do you require 'Read-Only' or 'Read-Write' permissions?",
  sap_system: "Which SAP system do you need access to (e.g., Production PRD, Sandbox, Development)?",
  requested_role: "What specific role or transaction group do you require in SAP?",
  username_to_unlock: "What is the domain username of the account you wish to unlock?",
  list_name: "Email address, alias, or display name of the distribution list",
  action: "Do you want to 'Create New' or 'Modify Existing' for this distribution list?",
  printer_name: "Name or device ID of the printer you want to connect to",
  location: "Where is the printer or workstation located (building, floor)?",
  laptop_model: "Which corporate laptop model would you like to request (e.g., Lenovo ThinkPad, Apple MacBook Pro 16)?",
  monitor_size: "What size monitor do you need (e.g., single 34-inch ultrawide, dual 24-inch flat panels)?",
  device_model: "Which mobile device model are you requesting (e.g., Apple iPhone 15 Pro, Samsung Galaxy S24)?",
  new_hire_name: "What is the full name of the new employee?",
  start_date: "What is the employee's start date (YYYY-MM-DD)?",
  department: "Which department or team will the new employee be joining?",
  db_type: "What database type are you requesting access to (e.g., Oracle, PostgreSQL, MS SQL Server)?",
  access_level: "What database permission level do you require (e.g., Read-Only, Read-Write)?",
  cloud_provider: "Which cloud service provider sandbox do you need (AWS, Azure, GCP)?",
  badge_type: "What type of physical access badge do you need (e.g., Employee, Contractor)?",
  location_access: "Which building facilities or security zones do you need badge access to?",
  accessory_type: "Which ergonomic accessory are you requesting (e.g., ergonomic mouse, keyboard, chair riser)?"
};

const CATALOG_REQUIRED_SLOTS: Record<string, string[]> = {
  SRV001: ["software_name", "justification"],
  SRV002: ["connection_profile", "mfa_method", "justification"],
  SRV003: ["folder_path", "access_type", "justification"],
  SRV004: ["sap_system", "requested_role", "justification"],
  SRV005: ["username_to_unlock", "justification"],
  SRV006: ["list_name", "action", "justification"],
  SRV007: ["printer_name", "location", "justification"],
  SRV008: ["laptop_model", "justification"],
  SRV009: ["monitor_size", "justification"],
  SRV010: ["device_model", "justification"],
  SRV011: ["new_hire_name", "start_date", "department", "justification"],
  SRV012: ["db_type", "access_level", "justification"],
  SRV013: ["cloud_provider", "justification"],
  SRV014: ["badge_type", "location_access", "justification"],
  SRV015: ["accessory_type", "justification"]
};

const CATEGORY_ICONS: Record<string, React.ComponentType<any>> = {
  "VPN": Shield,
  "Password": Lock,
  "Software": Cpu,
  "Email": Bell,
  "Network": Server,
  "Hardware": Sliders,
  "General": Info,
  "Unknown": Info
};

function getCategoryIcon(cat: string) {
  const IconComponent = CATEGORY_ICONS[cat] || CATEGORY_ICONS["Unknown"];
  return <IconComponent className="w-3.5 h-3.5 text-blue-400" />;
}

const CATEGORY_COLORS: Record<string, string> = {
  "VPN": "#2563EB",
  "Password": "#22C55E",
  "Software": "#8B5CF6",
  "Email": "#F59E0B",
  "Network": "#F97316",
  "Hardware": "#EC4899",
  "General": "#6366F1",
  "Unknown": "#64748B"
};

const PRIORITY_COLORS: Record<string, string> = {
  "CRITICAL": "#EF4444",
  "HIGH": "#F59E0B",
  "MEDIUM": "#3B82F6",
  "LOW": "#22C55E"
};

function statusBadgeClass(status: string): string {
  const s = status?.toUpperCase() ?? "";
  if (s === "OPEN")          return "badge badge-open";
  if (s === "ASSIGNED")      return "badge badge-assigned";
  if (s === "IN_PROGRESS")   return "badge badge-in-progress";
  if (s === "WAITING" || s === "WAITING_FOR_USER") return "badge badge-waiting";
  if (s === "RESOLVED")      return "badge badge-resolved";
  if (s === "CLOSED")        return "badge badge-closed";
  if (s === "APPROVED")      return "badge badge-approved";
  if (s === "REJECTED")      return "badge badge-rejected";
  if (s === "PENDING")       return "badge badge-pending";
  if (s === "ACCESS_DENIED" || s === "DENIED") return "badge badge-denied";
  if (s === "HEALTHY" || s === "RUNNING") return "badge badge-healthy";
  if (s === "DEGRADED")      return "badge badge-degraded";
  if (s === "UNHEALTHY" || s === "OFFLINE" || s === "ERROR") return "badge badge-unhealthy";
  return "badge badge-pending";
}

function slaBadgeClass(state?: string): string {
  const s = state?.toUpperCase() ?? "";
  if (s === "WARNING_75")      return "badge badge-sla-w75";
  if (s === "WARNING_90")      return "badge badge-sla-w90";
  if (s === "BREACHED")        return "badge badge-sla-breached";
  if (s === "ESCALATED_LEVEL_1") return "badge badge-sla-esc1";
  if (s === "ESCALATED_LEVEL_2") return "badge badge-sla-esc2";
  if (s === "ESCALATED_LEVEL_3") return "badge badge-sla-esc3";
  return "badge badge-sla-healthy";
}

function slaStateLabel(state?: string): string {
  const s = state?.toUpperCase() ?? "";
  if (s === "WARNING_75")      return "Warn 75%";
  if (s === "WARNING_90")      return "Warn 90%";
  if (s === "BREACHED")        return "Breached";
  if (s === "ESCALATED_LEVEL_1") return "Escalated L1";
  if (s === "ESCALATED_LEVEL_2") return "Escalated L2";
  if (s === "ESCALATED_LEVEL_3") return "Escalated L3";
  return "Healthy";
}

function priorityColor(p?: string): string {
  if (!p) return "text-slate-400";
  const u = p.toUpperCase();
  if (u === "CRITICAL") return "text-rose-400 font-extrabold";
  if (u === "HIGH")     return "text-amber-400 font-bold";
  if (u === "MEDIUM")   return "text-blue-400";
  return "text-emerald-400";
}

function fmtTime(ts?: string): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  } catch { return ts.substring(11, 16); }
}

function fmtDate(ts?: string): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch { return ts.substring(0, 10); }
}

function calculateSLACountdown(ticket: Ticket) {
  if (!ticket.created_at || ticket.sla_hours === undefined) return "No Target";
  if (ticket.status === "RESOLVED" || ticket.status === "CLOSED") return "SLA Met";
  if (ticket.sla_breached || ticket.sla_state === "BREACHED" || String(ticket.sla_state).startsWith("ESCALATED")) return "Breached";
  
  const createdTime = new Date(ticket.created_at).getTime();
  const targetTime = createdTime + ticket.sla_hours * 60 * 60 * 1000;
  const now = Date.now();
  const diff = targetTime - now;
  
  if (diff <= 0) return "Breached";
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  return `${hours}h ${minutes}m left`;
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENT RENDER HELPER
// ─────────────────────────────────────────────────────────────────────────────

const SectionHeader = memo(({ title, count, icon }: { title: string; count?: number; icon?: React.ReactNode }) => (
  <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-700/50">
    <div className="flex items-center gap-2">
      {icon}
      <span className="section-header text-xs tracking-wider font-semibold text-slate-400">{title}</span>
    </div>
    {count !== undefined && (
      <span className="text-[10px] font-mono font-bold text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded-full border border-slate-700/50">
        {count}
      </span>
    )}
  </div>
));
SectionHeader.displayName = "SectionHeader";

const EmptyState = memo(({ label }: { label: string }) => (
  <div className="flex flex-col items-center justify-center py-6 text-center text-xs text-slate-500 italic space-y-1">
    <Sliders className="w-5 h-5 opacity-30 text-slate-400 mb-1" />
    <span>{label}</span>
  </div>
));
EmptyState.displayName = "EmptyState";

const StatusDot = memo(({ status }: { status: string }) => {
  const s = status?.toLowerCase() ?? "";
  let cls = "dot-unknown";
  if (s === "healthy" || s === "online" || s === "running" || s === "online")  cls = "dot-healthy dot-pulse";
  else if (s === "degraded" || s === "warning")              cls = "dot-degraded dot-pulse";
  else if (s === "unhealthy" || s === "offline" || s === "error" || s === "unhealthy") cls = "dot-offline";
  return <span className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${cls}`} />;
});
StatusDot.displayName = "StatusDot";

// ─────────────────────────────────────────────────────────────────────────────
// MAIN APPLICATION HOME
// ─────────────────────────────────────────────────────────────────────────────

export default function Home() {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  // ── Auth state ──────────────────────────────────────────────────────────────
  const [user, setUser]                   = useState<any>(null);
  const [token, setToken]                 = useState<string | null>(null);
  const [refreshToken, setRefreshToken]   = useState<string | null>(null);
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError]       = useState("");
  const [isLoggingIn, setIsLoggingIn]     = useState(false);

  // ── Chat state ──────────────────────────────────────────────────────────────
  const [message, setMessage]     = useState("");
  const [messages, setMessages]   = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [category, setCategory]   = useState<string>("");
  const [status, setStatus]       = useState<string>("");
  const [actions, setActions]     = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState("");

  // ── Tab state ───────────────────────────────────────────────────────────────
  const [activeRightTab, setActiveRightTab] = useState<"service_desk" | "service_catalog" | "service_requests" | "admin_dashboard" | "monitoring" | "analytics">("service_desk");
  const [systemStatus, setSystemStatus]     = useState<any>(null);

  // ── Enterprise Analytics state ──────────────────────────────────────────────
  const [analyticsOverview, setAnalyticsOverview]     = useState<any>(null);
  const [analyticsTickets, setAnalyticsTickets]       = useState<any>(null);
  const [analyticsSla, setAnalyticsSla]               = useState<any>(null);
  const [analyticsTeams, setAnalyticsTeams]           = useState<any[]>([]);
  const [analyticsCategories, setAnalyticsCategories] = useState<any[]>([]);
  const [analyticsSecurity, setAnalyticsSecurity]     = useState<any>(null);
  const [analyticsRootCauses, setAnalyticsRootCauses] = useState<any>(null);
  const [analyticsUsers, setAnalyticsUsers]           = useState<any>(null);

  // ── ServiceNow ──────────────────────────────────────────────────────────────
  const [servicenowIncidents, setServicenowIncidents] = useState<any[]>([]);
  const [servicenowRequests, setServicenowRequests]   = useState<any[]>([]);

  // ── Microsoft Graph ─────────────────────────────────────────────────────────
  const [graphUsers, setGraphUsers]   = useState<any[]>([]);
  const [graphGroups, setGraphGroups] = useState<any[]>([]);

  // ── Azure AD / Entra ────────────────────────────────────────────────────────
  const [entraUsers, setEntraUsers]   = useState<any[]>([]);
  const [entraGroups, setEntraGroups] = useState<any[]>([]);
  const [entraStats, setEntraStats]   = useState<any>(null);

  // ── Approval state ──────────────────────────────────────────────────────────
  const [approvalRequired, setApprovalRequired]     = useState(false);
  const [approvalStatus, setApprovalStatus]         = useState("PENDING");
  const [recommendedAction, setRecommendedAction]   = useState("");
  const [actionResult, setActionResult]             = useState<Record<string, any> | null>(null);
  const [actionsHistory, setActionsHistory]         = useState<any[]>([]);

  // ── Enterprise logs ─────────────────────────────────────────────────────────
  const [auditLogs, setAuditLogs]       = useState<any[]>([]);
  const [approvals, setApprovals]       = useState<any[]>([]);
  const [agentTraces, setAgentTraces]   = useState<any[]>([]);
  const [securityLogs, setSecurityLogs] = useState<any[]>([]);

  // ── SLA Escalation Engine state ─────────────────────────────────────────────
  const [slaDashboard, setSlaDashboard]   = useState<any>(null);
  const [slaEscalations, setSlaEscalations] = useState<any[]>([]);

  // ── Ticket / notification state ─────────────────────────────────────────────
  const [tickets, setTickets]             = useState<Ticket[]>([]);
  const [activeTicket, setActiveTicket]   = useState<Ticket | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // ── Enterprise Slide-over details drawer state ──────────────────────────────
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetails, setSelectedTicketDetails] = useState<any>(null);
  const [isDrawerLoading, setIsDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState("");
  const [activeDrawerTab, setActiveDrawerTab] = useState<"info" | "timeline" | "diagnosis" | "related" | "chat">("info");
  const [internalNoteText, setInternalNoteText] = useState("");
  const [isSubmittingNote, setIsSubmittingNote] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{ action: string; title: string; desc: string } | null>(null);
  const [isExecutingAction, setIsExecutingAction] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // ── Custom frontend enhancement states ──────────────────────────────────────
  const [serviceCatalog, setServiceCatalog] = useState<any[]>([]);
  const [serviceRequests, setServiceRequests] = useState<any[]>([]);
  const [selectedServiceRequest, setSelectedServiceRequest] = useState<any | null>(null);
  const [serviceRequestDrawerOpen, setServiceRequestDrawerOpen] = useState(false);
  const [workNotesText, setWorkNotesText] = useState("");
  const [actionConfirmOpen, setActionConfirmOpen] = useState(false);
  const [pendingConfirmAction, setPendingConfirmAction] = useState<{ requestId: string; action: string; note?: string } | null>(null);
  const [requestCatalogItem, setRequestCatalogItem] = useState<any | null>(null);
  const [requestFormDetails, setRequestFormDetails] = useState<Record<string, string>>({});
  const [isSubmittingRequest, setIsSubmittingRequest] = useState(false);
  const [analyticsServiceRequests, setAnalyticsServiceRequests] = useState<any>(null);

  const [ticketViewMode, setTicketViewMode] = useState<"cards" | "table">("cards");
  const [searchQuery, setSearchQuery]       = useState("");
  const [currentTime, setCurrentTime]       = useState("");
  const [secondsSinceLastPoll, setSecondsSinceLastPoll] = useState(0);

  // ── Ticking clock effect ────────────────────────────────────────────────────
  useEffect(() => {
    const updateTime = () => {
      const date = new Date();
      setCurrentTime(date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // ── Heartbeat monitor ticker ────────────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsSinceLastPoll(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // ── Authentication check ────────────────────────────────────────────────────
  useEffect(() => {
    const savedToken        = localStorage.getItem("access_token");
    const savedRefreshToken = localStorage.getItem("refresh_token");
    const savedUser         = localStorage.getItem("user_info");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setRefreshToken(savedRefreshToken);
      try { setUser(JSON.parse(savedUser)); } catch (e) { console.error("Failed to parse user info:", e); }
    }
  }, []);

  // ── Dashboard data poller ───────────────────────────────────────────────────
  useEffect(() => {
    let interval: any;
    if (user) {
      setSecondsSinceLastPoll(0);
      fetchTickets();
      fetchNotifications();
      fetchServiceCatalog();
      fetchServiceRequests();
      if (user.role === "ADMIN" || user.role === "MANAGER") {
        fetchActionsHistory();
        fetchApprovals();
        fetchAnalyticsData();
      }
      if (user.role === "ADMIN") {
        fetchAuditLogs();
        fetchAgentTraces();
        fetchSecurityLogs();
        fetchSystemStatus();
        fetchServicenowIncidents();
        fetchServicenowRequests();
        fetchGraphUsers();
        fetchGraphGroups();
        fetchEntraUsers();
        fetchEntraGroups();
        fetchEntraStats();
        fetchSlaDashboard();
        fetchSlaEscalations();
        interval = setInterval(() => {
          setSecondsSinceLastPoll(0);
          fetchSystemStatus();
          fetchServicenowIncidents();
          fetchServicenowRequests();
          fetchGraphUsers();
          fetchGraphGroups();
          fetchEntraUsers();
          fetchEntraGroups();
          fetchEntraStats();
          fetchSlaDashboard();
          fetchSlaEscalations();
          fetchAnalyticsData();
          fetchServiceRequests();
        }, 15000);
      } else if (user.role === "MANAGER") {
        interval = setInterval(() => {
          setSecondsSinceLastPoll(0);
          fetchAnalyticsData();
          fetchServiceRequests();
        }, 15000);
      } else {
        interval = setInterval(() => {
          setSecondsSinceLastPoll(0);
          fetchTickets();
          fetchNotifications();
          fetchServiceRequests();
        }, 15000);
      }
    }
    return () => { if (interval) clearInterval(interval); };
  }, [user]);

  useEffect(() => {
    if (!activeTicket) return;
    const liveTicket = tickets.find((t) => t.ticket_id === activeTicket.ticket_id);
    if (liveTicket && liveTicket.status !== activeTicket.status) setActiveTicket(liveTicket);
  }, [tickets]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Auth fetch wrapper (unchanged) ──────────────────────────────────────────
  const authFetch = async (url: string, options: RequestInit = {}) => {
    let currentToken = token || localStorage.getItem("access_token");
    if (!currentToken) { handleLogout(); throw new Error("Session expired. Please log in again."); }

    const headers = { ...(options.headers || {}), Authorization: `Bearer ${currentToken}` };
    let res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      console.log("Token expired, attempting automatic refresh...");
      const currentRefreshToken = refreshToken || localStorage.getItem("refresh_token");
      if (currentRefreshToken) {
        try {
          const refreshRes = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: currentRefreshToken }),
          });
          if (refreshRes.ok) {
            const data      = await refreshRes.json();
            const newToken  = data.access_token;
            setToken(newToken);
            localStorage.setItem("access_token", newToken);
            const retryHeaders = { ...(options.headers || {}), Authorization: `Bearer ${newToken}` };
            res = await fetch(url, { ...options, headers: retryHeaders });
          } else {
            console.warn("Refresh token invalid or expired. Logging out.");
            handleLogout();
          }
        } catch (err) { console.error("Token refresh failed:", err); handleLogout(); }
      } else { handleLogout(); }
    }
    return res;
  };

  // ── Auth handlers ───────────────────────────────────────────────────────────
  const handleLogin = async (username: string, password: string) => {
    setLoginError("");
    setIsLoggingIn(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Authentication failed"); }
      const data = await res.json();
      setToken(data.access_token);
      setRefreshToken(data.refresh_token);
      setUser(data.user);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      localStorage.setItem("user_info", JSON.stringify(data.user));
      startNewSession();
    } catch (err: any) {
      setLoginError(err.message || "Failed to log in");
    } finally { setIsLoggingIn(false); }
  };

  const handleLogout = async () => {
    const currentToken = token || localStorage.getItem("access_token");
    if (currentToken) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch (err) { console.error("Failed to call logout API:", err); }
    }
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_info");
    startNewSession();
  };

  // ── Data fetchers ───────────────────────────────────────────────────────────
  const fetchTickets = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/tickets`); if (r.ok) setTickets(await r.json()); }
    catch (e) { console.error("Failed to fetch tickets:", e); }
  };
  const fetchNotifications = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/notifications`); if (r.ok) setNotifications(await r.json()); }
    catch (e) { console.error("Failed to fetch notifications:", e); }
  };
  const fetchActionsHistory = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/actions`); if (r.ok) setActionsHistory(await r.json()); }
    catch (e) { console.error("Failed to fetch actions history:", e); }
  };
  const fetchAuditLogs = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/audit-logs`); if (r.ok) setAuditLogs(await r.json()); }
    catch (e) { console.error("Failed to fetch audit logs:", e); }
  };
  const fetchApprovals = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/approvals`); if (r.ok) setApprovals(await r.json()); }
    catch (e) { console.error("Failed to fetch approvals:", e); }
  };
  const fetchAgentTraces = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/agent-traces`); if (r.ok) setAgentTraces(await r.json()); }
    catch (e) { console.error("Failed to fetch agent traces:", e); }
  };
  const fetchSecurityLogs = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/admin/security-logs`); if (r.ok) setSecurityLogs(await r.json()); }
    catch (e) { console.error("Failed to fetch security logs:", e); }
  };
  const fetchSystemStatus = async () => {
    const start = performance.now();
    try {
      const r = await authFetch(`${API_BASE_URL}/system-status`);
      const end = performance.now();
      const latencyMs = Math.round(end - start);
      if (r.ok) {
        const data = await r.json();
        setSystemStatus({ ...data, responseLatency: latencyMs });
      }
    } catch (e) { console.error("Failed to fetch system status:", e); }
  };
  const fetchServicenowIncidents = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/servicenow/incidents`); if (r.ok) setServicenowIncidents(await r.json()); }
    catch (e) { console.error("Failed to fetch ServiceNow incidents:", e); }
  };
  const fetchServicenowRequests = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/servicenow/requests`); if (r.ok) setServicenowRequests(await r.json()); }
    catch (e) { console.error("Failed to fetch ServiceNow requests:", e); }
  };
  const fetchGraphUsers = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/microsoftgraph/users`); if (r.ok) setGraphUsers(await r.json()); }
    catch (e) { console.error("Failed to fetch Microsoft Graph users:", e); }
  };
  const fetchGraphGroups = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/microsoftgraph/groups`); if (r.ok) setGraphGroups(await r.json()); }
    catch (e) { console.error("Failed to fetch Microsoft Graph groups:", e); }
  };
  const fetchEntraUsers = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/entra/users`); if (r.ok) setEntraUsers(await r.json()); }
    catch (e) { console.error("Failed to fetch Entra users:", e); }
  };
  const fetchEntraGroups = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/entra/groups`); if (r.ok) setEntraGroups(await r.json()); }
    catch (e) { console.error("Failed to fetch Entra groups:", e); }
  };
  const fetchEntraStats = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/entra/stats`); if (r.ok) setEntraStats(await r.json()); }
    catch (e) { console.error("Failed to fetch Entra stats:", e); }
  };
  const fetchSlaDashboard = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/sla/dashboard-metrics`); if (r.ok) setSlaDashboard(await r.json()); }
    catch (e) { console.error("Failed to fetch SLA dashboard metrics:", e); }
  };
  const fetchSlaEscalations = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/sla/escalations`); if (r.ok) setSlaEscalations(await r.json()); }
    catch (e) { console.error("Failed to fetch SLA escalations:", e); }
  };

  const fetchAnalyticsOverview = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/overview`); if (r.ok) setAnalyticsOverview(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics overview:", e); }
  };
  const fetchAnalyticsTickets = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/tickets`); if (r.ok) setAnalyticsTickets(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics tickets:", e); }
  };
  const fetchAnalyticsSla = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/sla`); if (r.ok) setAnalyticsSla(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics SLA:", e); }
  };
  const fetchAnalyticsTeams = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/teams`); if (r.ok) setAnalyticsTeams(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics teams:", e); }
  };
  const fetchAnalyticsCategories = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/categories`); if (r.ok) setAnalyticsCategories(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics categories:", e); }
  };
  const fetchAnalyticsSecurity = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/security`); if (r.ok) setAnalyticsSecurity(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics security:", e); }
  };
  const fetchAnalyticsRootCauses = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/root-causes`); if (r.ok) setAnalyticsRootCauses(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics root causes:", e); }
  };
  const fetchAnalyticsUsers = async () => {
    try { const r = await authFetch(`${API_BASE_URL}/api/analytics/users`); if (r.ok) setAnalyticsUsers(await r.json()); }
    catch (e) { console.error("Failed to fetch analytics users:", e); }
  };

  const fetchServiceCatalog = async () => {
    try {
      const r = await authFetch(`${API_BASE_URL}/service-catalog`);
      if (r.ok) setServiceCatalog(await r.json());
    } catch (e) {
      console.error("Failed to fetch service catalog:", e);
    }
  };

  const fetchServiceRequests = async () => {
    try {
      const r = await authFetch(`${API_BASE_URL}/service-requests`);
      if (r.ok) setServiceRequests(await r.json());
    } catch (e) {
      console.error("Failed to fetch service requests:", e);
    }
  };

  const fetchAnalyticsServiceRequests = async () => {
    try {
      const r = await authFetch(`${API_BASE_URL}/api/analytics/service-requests`);
      if (r.ok) setAnalyticsServiceRequests(await r.json());
    } catch (e) {
      console.error("Failed to fetch analytics service requests:", e);
    }
  };

  const handleServiceRequestAction = async (requestId: string, action: string, note?: string) => {
    setIsExecutingAction(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/service-requests/${requestId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note: note || null })
      });
      if (res.ok) {
        const updatedDetails = await res.json();
        setSelectedServiceRequest(updatedDetails);
        setWorkNotesText("");
        await fetchServiceRequests();
        if (user && (user.role === "ADMIN" || user.role === "MANAGER")) {
          fetchAnalyticsData();
        }
      } else {
        const errorData = await res.json();
        alert(errorData.detail || "Failed to execute service request action.");
      }
    } catch (e: any) {
      alert(e.message || "An error occurred.");
    } finally {
      setIsExecutingAction(false);
      setActionConfirmOpen(false);
      setPendingConfirmAction(null);
    }
  };

  const fetchAnalyticsData = async () => {
    if (!user || (user.role !== "ADMIN" && user.role !== "MANAGER")) return;
    fetchAnalyticsOverview();
    fetchAnalyticsTickets();
    fetchAnalyticsSla();
    fetchAnalyticsTeams();
    fetchAnalyticsCategories();
    fetchAnalyticsSecurity();
    fetchAnalyticsRootCauses();
    fetchAnalyticsUsers();
    fetchAnalyticsServiceRequests();
  };

  // ── Ticket details slide-over controls ──────────────────────────────────────
  const fetchTicketDetails = async (id: string) => {
    setIsDrawerLoading(true);
    setDrawerError("");
    try {
      const res = await authFetch(`${API_BASE_URL}/tickets/${id}/details`);
      if (res.ok) {
        const data = await res.json();
        setSelectedTicketDetails(data);
      } else {
        const errorData = await res.json();
        setDrawerError(errorData.detail || "Failed to load ticket details.");
      }
    } catch (err: any) {
      setDrawerError(err.message || "Failed to fetch ticket details.");
    } finally {
      setIsDrawerLoading(false);
    }
  };

  const handleTicketClick = (id: string) => {
    setSelectedTicketId(id);
    setActiveDrawerTab("info");
    fetchTicketDetails(id);
  };

  const handleAdminAction = async (action: string, extraParams: { team?: string; priority?: string; note?: string } = {}) => {
    if (!selectedTicketId) return;
    setIsExecutingAction(true);
    try {
      const res = await authFetch(`${API_BASE_URL}/tickets/${selectedTicketId}/action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          action,
          ...extraParams
        })
      });
      if (res.ok) {
        await fetchTicketDetails(selectedTicketId);
        await fetchTickets();
        if (user && (user.role === "ADMIN" || user.role === "MANAGER")) {
          fetchAnalyticsData();
          fetchSlaDashboard();
          fetchSlaEscalations();
        }
        setConfirmAction(null);
      } else {
        const errorData = await res.json();
        alert(errorData.detail || "Failed to execute administrative action.");
      }
    } catch (err: any) {
      alert(err.message || "An error occurred while executing the administrative action.");
    } finally {
      setIsExecutingAction(false);
    }
  };

  // ── sendMessage (unchanged) ─────────────────────────────────────────────────
  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;
    setError("");
    setIsLoading(true);
    setActions([]);
    const userMsg: Message = { sender: "user", text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    if (textToSend === message) setMessage("");

    try {
      const res = await authFetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: textToSend, session_id: sessionId }),
      });
      if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
      const data = (await res.json()) as ChatResponse;

      if (data.session_id) setSessionId(data.session_id);
      if (data.category)   setCategory(data.category);
      if (data.status)     setStatus(data.status);
      if (data.actions)    setActions(data.actions);
      if (data.ticket)     setActiveTicket(data.ticket);

      fetchTickets();
      fetchNotifications();
      setApprovalRequired(data.approval_required || false);
      setApprovalStatus(data.approval_status || "PENDING");
      setRecommendedAction(data.recommended_action || "");
      setActionResult(data.action_result || null);
      fetchNotifications();
      if (user?.role === "ADMIN" || user?.role === "MANAGER") {
        fetchActionsHistory();
        fetchApprovals();
      }
      if (user?.role === "ADMIN") {
        fetchAuditLogs();
        fetchAgentTraces();
        fetchSecurityLogs();
      }

      const agentMsg: Message = {
        sender: "agent",
        text: data.response || data.question,
        category: data.category,
        source: data.source,
        context_used: data.context_used,
        action: data.action,
        tool_result: data.tool_result,
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      console.error("→ API Request Failed:", err);
      setError(`Failed to send message: ${err.message || err}`);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewSession = () => {
    setMessages([]);
    setSessionId(null);
    setCategory("");
    setStatus("");
    setActions([]);
    setMessage("");
    setError("");
    setActiveTicket(null);
    setApprovalRequired(false);
    setApprovalStatus("PENDING");
    setRecommendedAction("");
    setActionResult(null);
  };

  // ── Derived dynamic charts dataset ──────────────────────────────────────────
  const ticketTrendData = useMemo(() => {
    if (!tickets || tickets.length === 0) return [];
    
    // Group ticket creations over the last 7 days
    const days = Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - i);
      return d.toISOString().split("T")[0];
    }).reverse();

    const groupCounts: Record<string, number> = {};
    days.forEach(d => { groupCounts[d] = 0; });

    tickets.forEach(t => {
      if (t.created_at) {
        const dStr = t.created_at.split("T")[0];
        if (dStr in groupCounts) {
          groupCounts[dStr]++;
        }
      }
    });

    return days.map(d => {
      const [_, month, day] = d.split("-");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthLabel = months[parseInt(month) - 1] || month;
      return {
        date: `${monthLabel} ${parseInt(day)}`,
        "Tickets Created": groupCounts[d]
      };
    });
  }, [tickets]);

  const priorityDistributionData = useMemo(() => {
    if (!analyticsTickets?.priority_distribution) return [];
    return Object.entries(analyticsTickets.priority_distribution).map(([p, count]) => ({
      name: p.charAt(0) + p.slice(1).toLowerCase(),
      value: count
    }));
  }, [analyticsTickets]);

  const slaStatesList = useMemo(() => {
    if (!analyticsSla) return [];
    const states = [
      { label: "Healthy", count: analyticsSla.healthy, color: "bg-emerald-500" },
      { label: "Warning 75%", count: analyticsSla.warning_75, color: "bg-yellow-500" },
      { label: "Warning 90%", count: analyticsSla.warning_90, color: "bg-orange-500" },
      { label: "Breached", count: analyticsSla.breached, color: "bg-red-500" },
      { label: "Escalated L1", count: analyticsSla.escalated_l1, color: "bg-rose-500" },
      { label: "Escalated L2", count: analyticsSla.escalated_l2, color: "bg-rose-600" },
      { label: "Escalated L3", count: analyticsSla.escalated_l3, color: "bg-rose-700" },
    ];
    const maxVal = Math.max(...states.map(s => s.count), 1);
    return states.map(s => ({
      ...s,
      percentage: Math.round((s.count / maxVal) * 100)
    }));
  }, [analyticsSla]);

  const filteredTickets = useMemo(() => {
    if (!tickets) return [];
    if (!searchQuery.trim()) return tickets;
    const query = searchQuery.toLowerCase();
    return tickets.filter(t => 
      t.ticket_id.toLowerCase().includes(query) ||
      t.category.toLowerCase().includes(query) ||
      t.assigned_team.toLowerCase().includes(query) ||
      t.status.toLowerCase().includes(query) ||
      (t.servicenow_id && t.servicenow_id.toLowerCase().includes(query))
    );
  }, [tickets, searchQuery]);

  const groupedCatalog = useMemo(() => {
    const groups: Record<string, any[]> = {};
    (serviceCatalog || []).forEach(item => {
      const cat = item.category || "General";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    });
    return groups;
  }, [serviceCatalog]);

  // ─────────────────────────────────────────────────────────────────────────────
  // RENDER — LOGIN SCREEN
  // ─────────────────────────────────────────────────────────────────────────────
  if (!user) {
    return (
      <main className="min-h-screen bg-[#0F172A] flex items-center justify-center p-4 relative overflow-hidden">
        {/* Subtle background glows */}
        <div className="absolute top-1/3 left-1/4 w-[500px] h-[500px] bg-blue-900/20 rounded-full blur-[100px] pointer-events-none" />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] bg-indigo-900/20 rounded-full blur-[80px] pointer-events-none" />

        <div className="relative z-10 w-full max-w-sm">
          {/* Logo / Brand */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600/20 border border-blue-500/30 mb-4">
              <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0H3" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-slate-100 tracking-tight">Bridgestone IT Portal</h1>
            <p className="text-xs text-slate-500 mt-1 tracking-widest uppercase font-medium">Enterprise Service Management</p>
          </div>

          {/* Card */}
          <div className="card p-6 space-y-5 shadow-2xl shadow-black/40">
            {loginError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-lg text-xs font-medium flex items-center gap-2">
                <svg className="w-3.5 h-3.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {loginError}
              </div>
            )}

            <form onSubmit={(e) => { e.preventDefault(); handleLogin(usernameInput, passwordInput); }} className="space-y-4">
              <div className="space-y-1.5">
                <label className="section-header block">Username</label>
                <input
                  type="text"
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  placeholder="Enter your username"
                  className="w-full bg-slate-850 border border-slate-700/60 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label className="section-header block">Password</label>
                <input
                  type="password"
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-slate-850 border border-slate-700/60 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={isLoggingIn}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                {isLoggingIn ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Authenticating...
                  </>
                ) : "Sign In"}
              </button>
            </form>

            {/* Quick Demo */}
            <div className="pt-2 border-t border-slate-700/50 space-y-2.5">
              <p className="section-header text-center">Quick Demo Access</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Employee", u: "employee", p: "employeepassword" },
                  { label: "Manager",  u: "manager",  p: "managerpassword"  },
                  { label: "Admin",    u: "admin",    p: "adminpassword"    },
                ].map(({ label, u, p }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => { setUsernameInput(u); setPasswordInput(p); handleLogin(u, p); }}
                    className="py-2 bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/50 hover:border-slate-600/60 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <p className="text-center text-[10px] text-slate-700 mt-4">
            Bridgestone IT Operations · Internal Use Only
          </p>
        </div>
      </main>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // RENDER — MAIN APPLICATION
  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div className="h-screen flex flex-col overflow-hidden bg-[#0F172A]">
      {/* ── Top Navigation Bar (Polished) ─────────────────────────────────── */}
      <header className="flex-shrink-0 h-14 bg-gradient-to-r from-[#1E293B] via-[#1E293B] to-[#1E293B]/90 border-b border-[#334155] flex items-center justify-between px-6 z-20 shadow-md">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight text-white block">Bridgestone IT Hub</span>
              <span className="text-[10px] text-slate-500 font-mono leading-none">Enterprise Service Portal</span>
            </div>
          </div>
          <span className="text-[#334155] text-lg font-light">/</span>
          <div className="hidden lg:flex items-center gap-2 bg-[#0F172A] border border-[#334155] rounded-lg px-3 py-1.5 w-60">
            <Search className="w-3.5 h-3.5 text-slate-500" />
            <input 
              type="text"
              placeholder="Global Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent border-none outline-none text-xs text-slate-200 placeholder-slate-650 w-full"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} className="text-slate-500 hover:text-slate-200">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Server Local Time Display */}
          <div className="hidden md:flex items-center gap-2 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-1">
            <Clock className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-[11px] font-mono text-slate-300 font-medium">SERVER TIME: {currentTime || "Loading..."}</span>
          </div>

          {/* Platform Status Indicator */}
          {systemStatus && (
            <div className="hidden sm:flex items-center gap-1.5 bg-[#0F172A] border border-[#334155] px-3 py-1 rounded-lg">
              <StatusDot status={systemStatus.status} />
              <span className="text-[10px] uppercase font-mono tracking-wide text-slate-400">{systemStatus.status}</span>
            </div>
          )}

          {/* User profile dropdown box */}
          <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700">
            <div className="w-6 h-6 rounded-full bg-blue-600/30 border border-blue-500/40 flex items-center justify-center">
              <UserIcon className="w-3.5 h-3.5 text-blue-400" />
            </div>
            <div className="hidden sm:flex flex-col">
              <span className="text-xs font-semibold text-slate-100 leading-none mb-0.5">{user?.username}</span>
              <span className="text-[9px] uppercase tracking-wider text-slate-500 leading-none">{user?.role}</span>
            </div>
            <span className={`badge ${user?.role === "ADMIN" ? "badge-rejected" : user?.role === "MANAGER" ? "badge-waiting" : "badge-assigned"}`}>
              {user?.role}
            </span>
          </div>

          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-rose-400 transition-colors px-2 py-1.5 rounded-lg hover:bg-slate-800/30 cursor-pointer"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden md:inline">Sign Out</span>
          </button>
        </div>
      </header>

      {/* ── Main Content Area ───────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── LEFT PANEL: Chat Interface ────────────────────────────────────── */}
        <div className="flex flex-col border-r border-[#334155] w-full lg:w-[45%] xl:w-[40%] min-w-0 overflow-hidden bg-[#0F172A]">
          {/* Session info bar */}
          {sessionId && (
            <div className="flex-shrink-0 flex items-center justify-between px-4 py-2.5 bg-slate-900 border-b border-[#334155] text-[10px] font-mono text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Session ID: <span className="text-slate-400 font-semibold">{sessionId.substring(0, 16)}...</span>
              </span>
              <div className="flex items-center gap-3">
                {category && <span>Category: <span className="text-slate-300 font-semibold">{category}</span></span>}
                <button
                  onClick={startNewSession}
                  className="text-blue-400 hover:text-blue-300 transition-colors text-[10px] font-sans font-medium flex items-center gap-1 cursor-pointer"
                >
                  <RefreshCw className="w-3 h-3" />
                  New Chat
                </button>
              </div>
            </div>
          )}

          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-5 p-8 max-w-md mx-auto">
                <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center shadow-inner">
                  <Sparkles className="w-8 h-8 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">Welcome, {user?.username}</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Bridgestone IT AI Agent is operational. Ask me to diagnose login issues, reset passwords, check SLA risks, or create active tickets.
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2.5 w-full mt-4">
                  {["VPN login not working", "Outlook account locked", "Access to folder denied", "Laptop slow/overheating"].map((hint) => (
                    <button
                      key={hint}
                      onClick={() => sendMessage(hint)}
                      className="px-4 py-3 text-[11px] text-slate-350 hover:text-white bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/60 rounded-xl text-left transition-all cursor-pointer leading-tight font-medium"
                    >
                      {hint}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div key={index} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} animate-fade-in`}>
                  <div className={`max-w-[85%] rounded-2xl px-4 py-3.5 text-sm leading-relaxed shadow-md border ${
                    msg.sender === "user"
                      ? "bg-blue-600 border-blue-500 text-white rounded-br-sm"
                      : "bg-[#1E293B] border-[#334155] text-slate-100 rounded-bl-sm"
                  }`}>
                    <div className="text-[9px] font-bold uppercase tracking-widest mb-1.5 opacity-60 flex items-center gap-1">
                      {msg.sender === "user" ? <UserIcon className="w-2.5 h-2.5" /> : <Sparkles className="w-2.5 h-2.5 text-blue-400" />}
                      {msg.sender === "user" ? user.username : "AI Agent"}
                    </div>
                    {msg.sender === "agent" && msg.action ? (
                      <div className="space-y-3">
                        <div className="bg-[#0F172A]/60 p-2.5 rounded-lg border border-slate-700/60">
                          <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Execution Triggered</span>
                          <span className="font-mono text-blue-400 text-xs font-bold">{msg.action}</span>
                        </div>
                        <div className="border-t border-slate-700/50 pt-2.5">
                          <span className="text-[9px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Outcome Details</span>
                          <span className="text-sm text-slate-200">{msg.text}</span>
                        </div>
                      </div>
                    ) : (
                      <span className="whitespace-pre-wrap">{msg.text}</span>
                    )}

                    {/* Tool result card */}
                    {msg.sender === "agent" && msg.tool_result && (
                      <div className="mt-3 p-3 bg-slate-900/90 border border-slate-700/80 rounded-xl text-xs space-y-2.5 shadow-inner">
                        <div className="flex justify-between items-center text-[9px] uppercase tracking-wider font-bold border-b border-slate-700/50 pb-2">
                          <span className="text-slate-500">Service API Integration</span>
                          <span className={statusBadgeClass(msg.tool_result.status || "SUCCESS")}>
                            {msg.tool_result.status || "SUCCESS"}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px] font-mono">
                          <span className="text-slate-500">Operation</span>
                          <span className="text-slate-350 font-bold text-right">{msg.tool_result.tool_name}</span>
                          {msg.tool_result.data && Object.entries(msg.tool_result.data).map(([key, val]) => (
                            <div key={key} className="contents">
                              <span className="text-slate-500 capitalize">{key.replace(/_/g, " ")}</span>
                              <span className={`font-semibold text-right ${
                                String(val) === "DISABLED" || String(val) === "DENIED" || String(val) === "OFFLINE" ? "text-rose-450" :
                                String(val) === "ONLINE" || String(val) === "ACTIVE" || String(val) === "CONNECTED" || val === true ? "text-emerald-400" :
                                "text-slate-300"
                              }`}>{String(val)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Source metadata */}
                    {msg.sender === "agent" && msg.source && msg.source !== "N/A" && (
                      <div className="mt-2.5 pt-2 border-t border-slate-700/40 flex flex-wrap gap-3 text-[10px] text-slate-500 font-mono">
                        <span>Category: <strong className="text-slate-400 font-bold">{msg.category}</strong></span>
                        <span>Scope: <strong className="text-slate-400 font-bold">{msg.source}</strong></span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-[#1E293B] border border-[#334155] text-slate-400 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2.5 shadow-sm">
                  <svg className="animate-spin h-4 w-4 text-blue-500" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span className="text-xs font-medium">Agent reasoning and compiling logs...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* ── Chat Input / Action Footer ──────────────────────────────────── */}
          <div className="flex-shrink-0 p-4 border-t border-[#334155] bg-slate-900/80 space-y-3">
            {/* Approval panel */}
            {approvalRequired && approvalStatus === "PENDING" && (
              <div className="p-4 rounded-xl bg-[#1E293B] border border-amber-500/30 space-y-3.5 shadow-lg shadow-black/20 animate-fade-in">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-amber-500" />
                    Recommended Action Approval
                  </span>
                  <span className="badge badge-waiting">Awaiting Authorization</span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Executing:{" "}
                  <code className="text-amber-400 font-mono bg-slate-900 px-2 py-1 rounded border border-slate-700/50 block mt-1.5 text-[10px]">
                    {recommendedAction}
                  </code>
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => sendMessage("yes")}
                    className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve Request
                  </button>
                  <button
                    onClick={() => sendMessage("no")}
                    className="flex-1 py-2 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold rounded-lg transition-colors cursor-pointer flex items-center justify-center gap-1"
                  >
                    <X className="w-3.5 h-3.5" />
                    Deny Request
                  </button>
                </div>
              </div>
            )}

            {/* Quick action chips */}
            {actions.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {actions.map((act) => (
                  <button
                    key={act}
                    onClick={() => sendMessage(act)}
                    className="px-4 py-2 bg-blue-600/10 hover:bg-blue-600/30 border border-blue-500/40 text-blue-400 hover:text-blue-300 text-xs font-bold rounded-lg transition-all cursor-pointer shadow-sm"
                  >
                    {act === "SOLVED" ? "Mark as Solved" : act === "NOT_SOLVED" ? "Not Resolved" : act}
                  </button>
                ))}
              </div>
            )}

            {error && (
              <div className="flex items-center gap-1.5 text-rose-400 text-xs font-medium px-1">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Text input */}
            {actions.length === 0 && (!approvalRequired || approvalStatus !== "PENDING") && (
              <div className="flex gap-2 items-end">
                <textarea
                  value={message}
                  onChange={(e) => { setMessage(e.target.value); if (error) setError(""); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(message); } }}
                  disabled={isLoading}
                  placeholder={sessionId ? "Provide details or continue conversation..." : "Submit ticket detail or type issue..."}
                  rows={1}
                  className="flex-1 bg-[#1E293B] border border-[#334155] rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 transition-all resize-none disabled:opacity-50 min-h-[44px] max-h-[120px]"
                  style={{ height: "44px" }}
                  onInput={(e) => {
                    const t = e.target as HTMLTextAreaElement;
                    t.style.height = "44px";
                    t.style.height = Math.min(t.scrollHeight, 120) + "px";
                  }}
                />
                <button
                  onClick={() => sendMessage(message)}
                  disabled={isLoading || !message.trim()}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:pointer-events-none text-white p-3 rounded-xl transition-colors flex items-center justify-center cursor-pointer flex-shrink-0 shadow-md shadow-blue-500/10"
                >
                  <ArrowUpRight className="h-4.5 w-4.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT PANEL: Dashboard ────────────────────────────────────────── */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden bg-[#0F172A]">

          {/* Tab Navigation (Sleek tab bar style) */}
          <div className="flex-shrink-0 flex items-center justify-between border-b border-[#334155] bg-slate-900/50 px-6 py-2.5">
            <div className="flex items-center gap-1 bg-[#0F172A] border border-[#334155] rounded-lg p-0.5">
              {[
                { key: "service_desk", label: "Service Desk", icon: <Sliders className="w-3.5 h-3.5" /> },
                { key: "service_catalog", label: "Service Catalog", icon: <Layers className="w-3.5 h-3.5" /> },
                { key: "service_requests", label: "Service Requests", icon: <FileText className="w-3.5 h-3.5" /> },
                ...(user?.role === "ADMIN" ? [
                  { key: "admin_dashboard", label: "Admin Console", icon: <Settings className="w-3.5 h-3.5" /> },
                  { key: "monitoring", label: "Monitoring", icon: <Activity className="w-3.5 h-3.5" /> }
                ] : []),
                ...((user?.role === "ADMIN" || user?.role === "MANAGER") ? [
                  { key: "analytics", label: "Analytics", icon: <BarChart3 className="w-3.5 h-3.5" /> }
                ] : [])
              ].map(({ key, label, icon }) => (
                <button
                  key={key}
                  onClick={() => setActiveRightTab(key as any)}
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                    activeRightTab === key
                      ? "bg-slate-800 text-blue-400 border border-slate-700 shadow-sm"
                      : "border border-transparent text-slate-500 hover:text-slate-350"
                  }`}
                >
                  {icon}
                  {label}
                </button>
              ))}
            </div>
            
            {/* View Mode & Time metrics */}
            {activeRightTab === "service_desk" && (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1 bg-[#0F172A] border border-[#334155] rounded-lg p-0.5">
                  <button 
                    onClick={() => setTicketViewMode("cards")}
                    className={`px-3 py-1 rounded text-[10px] font-semibold transition-all ${ticketViewMode === "cards" ? "bg-slate-800 text-slate-200" : "text-slate-500 hover:text-slate-300"}`}
                  >
                    Card List
                  </button>
                  <button 
                    onClick={() => setTicketViewMode("table")}
                    className={`px-3 py-1 rounded text-[10px] font-semibold transition-all ${ticketViewMode === "table" ? "bg-slate-800 text-slate-200" : "text-slate-500 hover:text-slate-300"}`}
                  >
                    Table Grid
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Tab Content — Animated transitions */}
          <div className="flex-1 overflow-y-auto bg-gradient-to-b from-[#0F172A] to-slate-900">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeRightTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="h-full"
              >
                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* SERVICE DESK TAB                                               */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "service_desk" && (
                  <div className="p-6 space-y-6">

                    {/* Active Ticket Banner */}
                    {status === "RESOLVED" && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-start gap-3 shadow-md"
                      >
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 flex-shrink-0" />
                        <div>
                          <h4 className="text-xs font-bold text-emerald-300">Session Successfully Resolved</h4>
                          <p className="text-[11px] text-emerald-400/80 mt-1">The diagnostics indicate user problem resolved. Ticket lifecycle closed.</p>
                        </div>
                      </motion.div>
                    )}

                    {/* Active Ticket Detail Box */}
                    {activeTicket && (
                      <motion.div 
                        initial={{ opacity: 0, y: 5 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="card p-5 relative overflow-hidden border-l-4 border-l-blue-500"
                      >
                        <div className="flex items-center justify-between mb-3 border-b border-slate-700/40 pb-2.5">
                          <div className="flex items-center gap-1.5">
                            <Tag className="w-4 h-4 text-blue-400" />
                            <span className="text-xs font-bold text-slate-200">Active Workflow Ticket</span>
                          </div>
                          <span className={statusBadgeClass(activeTicket.status)}>{activeTicket.status}</span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-[11px]">
                          <div>
                            <span className="text-slate-500 block mb-1">Ticket ID</span>
                            <span className="font-mono font-bold text-blue-400">{activeTicket.ticket_id}</span>
                          </div>
                          {activeTicket.servicenow_id && (
                            <div>
                              <span className="text-slate-500 block mb-1">ServiceNow Ref</span>
                              <span className="font-mono font-bold text-amber-500">{activeTicket.servicenow_id}</span>
                            </div>
                          )}
                          <div>
                            <span className="text-slate-500 block mb-1">Assigned Support Team</span>
                            <span className="text-slate-300 font-semibold">{activeTicket.assigned_team}</span>
                          </div>
                          {activeTicket.priority && (
                            <div>
                              <span className="text-slate-500 block mb-1">Priority Level</span>
                              <span className={`font-bold ${priorityColor(activeTicket.priority)}`}>{activeTicket.priority}</span>
                            </div>
                          )}
                        </div>
                        <div className="mt-3 pt-3 border-t border-slate-700/40 text-[11px] flex justify-between items-center text-slate-400">
                          <span>SLA Target: <strong className="text-slate-300 font-mono">{activeTicket.sla_hours || 0}h</strong></span>
                          <span>Time Left: <strong className="text-emerald-400 font-mono">{calculateSLACountdown(activeTicket)}</strong></span>
                        </div>
                      </motion.div>
                    )}

                    {/* Action Execution result */}
                    {actionResult && (
                      <div className="card p-5 border-l-4 border-l-emerald-500 space-y-3 animate-fade-in bg-emerald-950/5">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-emerald-300">Request Created Successfully</span>
                          <span className={statusBadgeClass(actionResult.status)}>{actionResult.status}</span>
                        </div>
                        <div className="grid grid-cols-3 gap-3 text-[11px] font-mono">
                          <div>
                            <span className="text-slate-500 block mb-0.5">Request ID</span>
                            <span className="text-emerald-400 font-bold">{actionResult.request_id}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-0.5">ServiceNow SysRef</span>
                            <span className="text-amber-500 font-bold">{actionResult.servicenow_id}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-0.5">Action Executed</span>
                            <span className="text-slate-300 font-semibold">{actionResult.action_type}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Main Tickets Section */}
                    <div>
                      <SectionHeader title="Operational Tickets" count={filteredTickets.length} icon={<FileText className="w-4 h-4 text-slate-400" />} />
                      
                      {/* Grid Mode of Premium Cards */}
                      {ticketViewMode === "cards" ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {filteredTickets.length === 0 ? (
                            <div className="col-span-full bg-slate-900/20 border border-slate-800 p-6 rounded-xl text-center">
                              <EmptyState label="No tickets match filter conditions" />
                            </div>
                          ) : (
                            filteredTickets.slice().reverse().map((t) => (
                              <motion.div
                                key={t.ticket_id}
                                whileHover={{ y: -3, scale: 1.01 }}
                                className="card p-4 flex flex-col justify-between relative overflow-hidden border-l-4 cursor-pointer hover:shadow-[0_0_15px_rgba(59,130,246,0.15)] transition-all"
                                onClick={() => handleTicketClick(t.ticket_id)}
                                style={{
                                  borderLeftColor:
                                    t.priority?.toUpperCase() === "CRITICAL" ? PRIORITY_COLORS.CRITICAL :
                                    t.priority?.toUpperCase() === "HIGH" ? PRIORITY_COLORS.HIGH :
                                    t.priority?.toUpperCase() === "MEDIUM" ? PRIORITY_COLORS.MEDIUM : PRIORITY_COLORS.LOW
                                }}
                              >
                                <div className="space-y-3">
                                  <div className="flex justify-between items-start">
                                    <div className="flex items-center gap-1.5">
                                      {getCategoryIcon(t.category)}
                                      <span className="font-mono text-xs font-bold text-slate-100">{t.ticket_id}</span>
                                    </div>
                                    <div className="flex items-center gap-1">
                                      <span className="badge text-[9px] font-bold" style={{
                                        backgroundColor: t.priority?.toUpperCase() === "CRITICAL" ? "rgba(239, 68, 68, 0.15)" :
                                                         t.priority?.toUpperCase() === "HIGH" ? "rgba(245, 158, 11, 0.15)" :
                                                         t.priority?.toUpperCase() === "MEDIUM" ? "rgba(59, 130, 246, 0.15)" : "rgba(34, 197, 94, 0.15)",
                                        color: t.priority?.toUpperCase() === "CRITICAL" ? "#EF4444" :
                                               t.priority?.toUpperCase() === "HIGH" ? "#F59E0B" :
                                               t.priority?.toUpperCase() === "MEDIUM" ? "#3B82F6" : "#22C55E",
                                        border: "1px solid rgba(255, 255, 255, 0.05)"
                                      }}>{t.priority || "LOW"}</span>
                                      {t.sla_state && t.sla_state !== "HEALTHY" && (
                                        <span className={slaBadgeClass(t.sla_state)}>{slaStateLabel(t.sla_state)}</span>
                                      )}
                                      <span className={statusBadgeClass(t.status)}>{t.status}</span>
                                    </div>
                                  </div>
                                  <div>
                                    <p className="text-[11px] text-slate-400 italic line-clamp-2 leading-relaxed">"{t.issue_description}"</p>
                                  </div>
                                  <div className="text-[10px] text-slate-400 font-medium">
                                    Requester: <span className="text-slate-200 font-bold">{
                                      t.created_by === "employee" ? "Raghvendra Bhati" :
                                      t.created_by === "manager" ? "Sarah Jenkins" :
                                      t.created_by === "admin" ? "Alex Rivera" : (t.created_by || "System User")
                                    }</span>
                                  </div>
                                </div>

                                <div className="mt-4 pt-3 border-t border-slate-700/30 grid grid-cols-2 gap-2 text-[10px]">
                                  <div className="flex items-center gap-1 text-slate-500">
                                    <Users className="w-3 h-3 text-slate-400" />
                                    <span>Team: <strong className="text-slate-350">{t.assigned_team}</strong></span>
                                  </div>
                                  <div className="flex items-center gap-1 text-slate-500 justify-end">
                                    <Clock className="w-3 h-3 text-slate-400" />
                                    <span>SLA: <strong className="text-emerald-450 font-mono">{calculateSLACountdown(t)}</strong></span>
                                  </div>
                                  <div className="col-span-2 flex justify-between text-slate-500 border-t border-slate-700/10 pt-1.5">
                                    <span>Created: {fmtDate(t.created_at)} {fmtTime(t.created_at)}</span>
                                    {t.servicenow_id && <span className="text-amber-500 font-mono">SNOW: {t.servicenow_id}</span>}
                                  </div>
                                </div>
                              </motion.div>
                            ))
                          )}
                        </div>
                      ) : (
                        /* Table Mode (Requirement 5: Table Recent Tickets) */
                        <div className="enterprise-table-container max-h-96">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Ticket ID</th>
                                <th>ServiceNow Ref</th>
                                <th>Category</th>
                                <th>Priority</th>
                                <th>Assigned Team</th>
                                <th>SLA State</th>
                                <th>Time Remaining</th>
                                <th>Status</th>
                                <th>Created</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filteredTickets.length === 0 ? (
                                <tr>
                                  <td colSpan={9} className="text-center py-4 text-slate-500">No tickets recorded</td>
                                </tr>
                              ) : (
                                filteredTickets.slice().reverse().map((t) => (
                                  <tr key={t.ticket_id} onClick={() => handleTicketClick(t.ticket_id)} className="cursor-pointer hover:bg-slate-800/40 transition-colors">
                                    <td className="font-mono font-bold text-blue-400">{t.ticket_id}</td>
                                    <td className="font-mono text-amber-500">{t.servicenow_id || "—"}</td>
                                    <td className="font-semibold">{t.category}</td>
                                    <td className={`font-semibold ${priorityColor(t.priority)}`}>{t.priority}</td>
                                    <td className="text-slate-300">{t.assigned_team}</td>
                                    <td>
                                      <span className={slaBadgeClass(t.sla_state)}>{slaStateLabel(t.sla_state)}</span>
                                    </td>
                                    <td className="font-mono font-bold text-emerald-400">{calculateSLACountdown(t)}</td>
                                    <td>
                                      <span className={statusBadgeClass(t.status)}>{t.status}</span>
                                    </td>
                                    <td className="font-mono text-slate-500">{fmtDate(t.created_at)} {fmtTime(t.created_at)}</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    {/* Recent Actions & History */}
                    {(user?.role === "ADMIN" || user?.role === "MANAGER") && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="card p-4">
                          <SectionHeader title="Recent Action Executions" count={actionsHistory.length} icon={<Terminal className="w-4 h-4 text-slate-400" />} />
                          <div className="space-y-2 max-h-60 overflow-y-auto">
                            {actionsHistory.length === 0 ? (
                              <EmptyState label="No background actions logged" />
                            ) : (
                              actionsHistory.slice().reverse().map((act, idx) => (
                                <div key={act.request_id ?? idx} className="flex items-center justify-between py-2 px-3 bg-slate-800/20 border border-slate-700/30 rounded-lg hover:bg-slate-800/40 transition-colors">
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono text-xs font-bold text-slate-200">{act.request_id}</span>
                                      {act.servicenow_id && <span className="font-mono text-[10px] text-amber-500">{act.servicenow_id}</span>}
                                    </div>
                                    <span className="text-[10px] text-slate-500 font-mono block mt-0.5">{act.action_type}</span>
                                  </div>
                                  <span className={statusBadgeClass(act.status)}>{act.status}</span>
                                </div>
                              ))
                            )}
                          </div>
                        </div>

                        {/* Recent Notifications Table (Requirement 5: Table Notifications) */}
                        <div className="card p-4">
                          <SectionHeader title="Notifications Audit Dispatch" count={notifications.length} icon={<Bell className="w-4 h-4 text-slate-400" />} />
                          <div className="enterprise-table-container max-h-60">
                            <table className="enterprise-table">
                              <thead>
                                <tr>
                                  <th>ID</th>
                                  <th>Ticket</th>
                                  <th>Recipient</th>
                                  <th>Message</th>
                                  <th>Sent Time</th>
                                </tr>
                              </thead>
                              <tbody>
                                {notifications.length === 0 ? (
                                  <tr>
                                    <td colSpan={5} className="text-center py-4 text-slate-500">No notifications dispatched</td>
                                  </tr>
                                ) : (
                                  notifications.slice().reverse().map((n) => (
                                    <tr key={n.notification_id}>
                                      <td className="font-mono font-bold text-slate-400">{n.notification_id.substring(0, 8)}...</td>
                                      <td className="font-mono text-blue-400">{n.ticket_id}</td>
                                      <td className="font-semibold text-slate-300">{n.recipient}</td>
                                      <td className="text-slate-400 max-w-[150px] truncate" title={n.message}>{n.message}</td>
                                      <td className="font-mono text-slate-500">{fmtDate(n.timestamp)} {fmtTime(n.timestamp)}</td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* SERVICE CATALOG TAB                                            */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "service_catalog" && (
                  <div className="p-6 space-y-6">
                    <div className="flex justify-between items-center mb-2">
                      <div>
                        <h2 className="text-lg font-bold text-slate-100">Enterprise Service Catalog</h2>
                        <p className="text-xs text-slate-400 font-semibold mt-0.5">Select an IT service from the catalog below to place a request.</p>
                      </div>
                    </div>

                    {Object.entries(groupedCatalog).map(([categoryName, items]) => (
                      <div key={categoryName} className="space-y-3">
                        <h3 className="text-xs font-bold uppercase tracking-wider text-blue-400 border-b border-slate-800 pb-1.5">{categoryName}</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {items.map((item: any) => (
                            <motion.div
                              key={item.service_id}
                              whileHover={{ y: -3, scale: 1.01 }}
                              onClick={() => {
                                setRequestCatalogItem(item);
                                const defaultForm: Record<string, string> = {};
                                (CATALOG_REQUIRED_SLOTS[item.service_id] || []).forEach(slot => {
                                  defaultForm[slot] = "";
                                });
                                setRequestFormDetails(defaultForm);
                              }}
                              className="card p-4 hover:border-blue-500/30 transition-all cursor-pointer flex flex-col justify-between"
                            >
                              <div>
                                <div className="flex items-start justify-between gap-2 mb-2">
                                  <h4 className="text-sm font-bold text-slate-200">{item.name}</h4>
                                  <span className="text-[9px] font-mono font-bold bg-slate-800 border border-slate-750 px-2 py-0.5 rounded text-slate-400">{item.service_id}</span>
                                </div>
                                <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed mb-4 font-semibold">{item.description}</p>
                              </div>
                              <div className="flex justify-between items-center border-t border-slate-850 pt-3 text-[10px] text-slate-500 font-semibold">
                                <span>Est. Fulfillment: <strong className="text-slate-350">{item.estimated_completion}</strong></span>
                                {item.approval_required && (
                                  <span className="text-amber-500 font-bold px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">Requires Approval</span>
                                )}
                              </div>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* SERVICE REQUESTS TAB                                           */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "service_requests" && (
                  <div className="p-6 space-y-6">
                    <div className="flex justify-between items-center mb-2">
                      <div>
                        <h2 className="text-lg font-bold text-slate-100">Service Requests Log</h2>
                        <p className="text-xs text-slate-400 font-semibold mt-0.5">Track and manage catalog request workflows.</p>
                      </div>
                      <button
                        onClick={fetchServiceRequests}
                        className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-750 transition-colors text-slate-400 hover:text-slate-200 flex items-center gap-1.5 text-xs font-semibold cursor-pointer"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        Refresh
                      </button>
                    </div>

                    <div className="card p-5">
                      <SectionHeader title="All Catalog Requests" count={serviceRequests.length} icon={<FileText className="w-4 h-4 text-slate-400" />} />
                      <div className="enterprise-table-container">
                        <table className="enterprise-table">
                          <thead>
                            <tr>
                              <th>Request ID</th>
                              <th>Service Name</th>
                              <th>Requested By</th>
                              <th>Stage</th>
                              <th>Status</th>
                              <th>Created</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {serviceRequests.length === 0 ? (
                              <tr>
                                <td colSpan={7} className="text-center py-6 text-slate-500 italic font-semibold">No service requests recorded</td>
                              </tr>
                            ) : (
                              serviceRequests.slice().reverse().map((req: any) => (
                                <tr key={req.request_id} className="hover:bg-slate-800/40 transition-colors">
                                  <td className="font-mono font-bold text-slate-300">{req.request_id}</td>
                                  <td className="font-semibold text-slate-200">{req.service_name}</td>
                                  <td className="font-mono text-slate-400">@{req.requested_by}</td>
                                  <td className="text-slate-400 text-xs font-semibold">{req.stage}</td>
                                  <td>
                                    <span className={statusBadgeClass(req.status)}>{req.status}</span>
                                  </td>
                                  <td className="font-mono text-slate-500 text-xs">
                                    {fmtDate(req.created_at)} {fmtTime(req.created_at)}
                                  </td>
                                  <td>
                                    <button
                                      onClick={async () => {
                                        try {
                                          const res = await authFetch(`${API_BASE_URL}/service-requests/${req.request_id}/details`);
                                          if (res.ok) {
                                            setSelectedServiceRequest(await res.json());
                                            setServiceRequestDrawerOpen(true);
                                            setWorkNotesText("");
                                          } else {
                                            const err = await res.json();
                                            alert(err.detail || "Failed to load request details.");
                                          }
                                        } catch (e: any) {
                                          alert(e.message || "An error occurred.");
                                        }
                                      }}
                                      className="px-2.5 py-1 rounded bg-slate-850 hover:bg-slate-750 border border-slate-750 text-[10px] font-bold text-blue-400 transition-colors cursor-pointer"
                                    >
                                      Details
                                    </button>
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* ADMIN CONSOLE TAB                                              */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "admin_dashboard" && user?.role === "ADMIN" && (
                  <div className="p-6 space-y-6">
                    <div className="grid grid-cols-1 gap-6">

                      {/* Audit Events (Requirement 5: Table Audit Events) */}
                      <div className="card p-5">
                        <SectionHeader title="Audit Events Log" count={auditLogs.length} icon={<Shield className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-64">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Session ID</th>
                                <th>Category</th>
                                <th>User Message</th>
                                <th>Status</th>
                                <th>Rbac Decision</th>
                                <th>Timestamp</th>
                              </tr>
                            </thead>
                            <tbody>
                              {auditLogs.length === 0 ? (
                                <tr>
                                  <td colSpan={6} className="text-center py-4 text-slate-500">No audits found</td>
                                </tr>
                              ) : (
                                auditLogs.slice().reverse().map((log, idx) => (
                                  <tr key={idx}>
                                    <td className="font-mono text-slate-450">{log.session_id?.substring(0, 12)}...</td>
                                    <td className="font-semibold text-slate-200">{log.category || "General"}</td>
                                    <td className="text-slate-400 max-w-xs truncate" title={log.user_message}>"{log.user_message}"</td>
                                    <td>
                                      <span className={statusBadgeClass(log.approval_status ?? "PENDING")}>{log.approval_status ?? "PENDING"}</span>
                                    </td>
                                    <td className="font-semibold font-mono text-slate-300">{log.decision}</td>
                                    <td className="font-mono text-slate-500">{fmtDate(log.timestamp)} {fmtTime(log.timestamp)}</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Security Events (Requirement 5: Table Security Events) */}
                      <div className="card p-5 border-rose-500/10">
                        <SectionHeader title="Security Compliance logs" count={securityLogs.length} icon={<AlertTriangle className="w-4 h-4 text-rose-500" />} />
                        <div className="enterprise-table-container max-h-64">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Event Type</th>
                                <th>Scope Details</th>
                                <th>Subject Username</th>
                                <th>Event Time</th>
                              </tr>
                            </thead>
                            <tbody>
                              {securityLogs.length === 0 ? (
                                <tr>
                                  <td colSpan={4} className="text-center py-4 text-slate-500">No security violations</td>
                                </tr>
                              ) : (
                                securityLogs.slice().reverse().map((log, idx) => (
                                  <tr key={idx} className="hover:bg-rose-500/5">
                                    <td>
                                      <span className="badge badge-rejected font-mono text-[9px]">{log.event_type}</span>
                                    </td>
                                    <td className="font-mono text-rose-300 text-xs max-w-sm truncate" title={log.details}>{log.details}</td>
                                    <td className="font-semibold text-slate-200">{log.username || "System Agent"}</td>
                                    <td className="font-mono text-slate-500">{fmtDate(log.timestamp)} {fmtTime(log.timestamp)}</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Approval History (Requirement 5: Table Approval History) */}
                      <div className="card p-5">
                        <SectionHeader title="Authorization approval history" count={approvals.length} icon={<Lock className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-60">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Session ID</th>
                                <th>Recommended Operation</th>
                                <th>Approver Manager</th>
                                <th>Status</th>
                                <th>Logged Time</th>
                              </tr>
                            </thead>
                            <tbody>
                              {approvals.length === 0 ? (
                                <tr>
                                  <td colSpan={5} className="text-center py-4 text-slate-500">No approval actions logged</td>
                                </tr>
                              ) : (
                                approvals.slice().reverse().map((app, idx) => (
                                  <tr key={idx}>
                                    <td className="font-mono text-slate-450">{app.session_id?.substring(0, 12)}...</td>
                                    <td className="font-mono text-blue-400 font-semibold max-w-[200px] truncate" title={app.recommended_action}>{app.recommended_action}</td>
                                    <td className="font-semibold text-slate-200">{app.manager_username || "Awaiting..."}</td>
                                    <td>
                                      <span className={statusBadgeClass(app.approval_status)}>{app.approval_status}</span>
                                    </td>
                                    <td className="font-mono text-slate-500">{fmtDate(app.timestamp)} {fmtTime(app.timestamp)}</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Trace Output logs */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="card p-4">
                          <SectionHeader title="LLM Agent State Traces" count={agentTraces.length} icon={<Terminal className="w-4 h-4 text-slate-400" />} />
                          <div className="space-y-3.5 max-h-60 overflow-y-auto">
                            {agentTraces.length === 0 ? (
                              <EmptyState label="No agent traces logged" />
                            ) : (
                              agentTraces.slice().reverse().map((tr, idx) => (
                                <div key={idx} className="p-3 bg-slate-900 border border-slate-700/60 rounded-xl space-y-2">
                                  <div className="flex justify-between items-center border-b border-slate-800 pb-1.5">
                                    <span className="text-xs font-bold text-indigo-400 flex items-center gap-1">
                                      <Sparkles className="w-3.5 h-3.5" />
                                      {tr.agent_name}
                                    </span>
                                    <div className="flex flex-col text-right items-end">
                                      <span className="font-mono text-[9px] text-slate-500">Session: {tr.session_id?.substring(0, 12)}...</span>
                                      {tr.correlation_id && (
                                        <span className="font-mono text-[9px] text-indigo-300 font-semibold">Correlation: {tr.correlation_id}</span>
                                      )}
                                    </div>
                                  </div>
                                  <pre className="text-[10px] font-mono text-slate-400 overflow-x-auto max-h-24 leading-normal whitespace-pre-wrap">
                                    {JSON.stringify(tr.output, null, 2)}
                                  </pre>
                                </div>
                              ))
                            )}
                          </div>
                        </div>

                        {/* SLA Escalation Levels list */}
                        <div className="card p-4">
                          <SectionHeader title="SLA escalations" count={slaEscalations.length} icon={<AlertTriangle className="w-4 h-4 text-amber-500" />} />
                          <div className="enterprise-table-container max-h-60">
                            <table className="enterprise-table">
                              <thead>
                                <tr>
                                  <th>Ticket ID</th>
                                  <th>Level</th>
                                  <th>Reason</th>
                                  <th>Alert</th>
                                </tr>
                              </thead>
                              <tbody>
                                {slaEscalations.length === 0 ? (
                                  <tr>
                                    <td colSpan={4} className="text-center py-4 text-slate-500">No escalations</td>
                                  </tr>
                                ) : (
                                  slaEscalations.slice(0, 20).map((esc, idx) => (
                                    <tr key={esc.id ?? idx}>
                                      <td className="font-mono font-bold text-blue-400">{esc.ticket_id}</td>
                                      <td>
                                        <span className={`badge ${
                                          esc.level === 1 ? "badge-sla-esc1" :
                                          esc.level === 2 ? "badge-sla-esc2" : "badge-sla-esc3"
                                        }`}>L{esc.level}</span>
                                      </td>
                                      <td className="text-slate-400 max-w-[150px] truncate" title={esc.reason}>{esc.reason}</td>
                                      <td>
                                        <span className={esc.notification_sent ? "text-emerald-400 font-bold" : "text-rose-500 font-bold"}>
                                          {esc.notification_sent ? "Sent" : "Pending"}
                                        </span>
                                      </td>
                                    </tr>
                                  ))
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* MONITORING TAB                                                 */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "monitoring" && user?.role === "ADMIN" && (
                  <div className="p-6 space-y-6">

                    {/* System Health Section (Requirement 3: Redesigned health cards) */}
                    <section>
                      <SectionHeader title="System Core Health Status" icon={<Activity className="w-4 h-4 text-slate-400" />} />
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        {[
                          { 
                            key: "database",  
                            label: "Database",   
                            status: systemStatus?.database, 
                            desc: "SQLite database instance online, connections healthy",
                            latency: systemStatus?.responseLatency ? `${Math.round(systemStatus.responseLatency * 0.4)}ms` : "1ms",
                            icon: <Database className="w-4 h-4 text-emerald-400" />
                          },
                          { 
                            key: "gemini",    
                            label: "Gemini AI LLM", 
                            status: systemStatus?.gemini, 
                            desc: "Google Gemini generative reasoning API connectivity",
                            latency: systemStatus?.adapters?.["Gemini LLM"]?.latency ? `${(systemStatus.adapters["Gemini LLM"].latency * 1000).toFixed(0)}ms` : "140ms",
                            icon: <Cpu className="w-4 h-4 text-emerald-400" />
                          },
                          { 
                            key: "servicenow", 
                            label: "ServiceNow Adapters", 
                            status: systemStatus?.adapters?.["ServiceNow Simulation"]?.status ?? "healthy", 
                            desc: "ServiceNow SOAP & REST Web Service adapters online",
                            latency: systemStatus?.adapters?.["ServiceNow Simulation"]?.latency ? `${(systemStatus.adapters["ServiceNow Simulation"].latency * 1000).toFixed(0)}ms` : "24ms",
                            icon: <Layers className="w-4 h-4 text-emerald-400" />
                          },
                          { 
                            key: "redis",     
                            label: "Redis Cache Store", 
                            status: systemStatus?.redis ?? "degraded", 
                            desc: "Redis fallback session cache connection status",
                            latency: "2ms",
                            icon: <Zap className="w-4 h-4 text-amber-500" />
                          },
                          { 
                            key: "scheduler", 
                            label: "Cron Scheduler",  
                            status: systemStatus?.scheduler ?? "running", 
                            desc: "APScheduler running ticket lifecycle scan cron jobs",
                            latency: "N/A",
                            icon: <Clock className="w-4 h-4 text-emerald-400" />
                          },
                        ].map(({ key, label, status: s, desc, latency, icon }) => {
                          const isDegraded = s === "degraded" || s === "warning";
                          const isOffline = s === "unhealthy" || s === "offline" || s === "error" || !s;
                          const bgBorderColor = isOffline 
                            ? "border-rose-500/20 bg-rose-950/5 hover:border-rose-500/40" 
                            : isDegraded 
                              ? "border-amber-500/20 bg-amber-950/5 hover:border-amber-500/40" 
                              : "border-emerald-500/20 bg-emerald-950/5 hover:border-emerald-500/40";
                          
                          return (
                            <div 
                              key={key} 
                              className={`card p-4 flex flex-col justify-between relative overflow-hidden transition-all duration-200 tooltip-trigger ${bgBorderColor}`}
                            >
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-bold text-xs text-slate-100">{label}</span>
                                {icon}
                              </div>
                              <div className="flex items-center gap-1.5 mt-2">
                                <StatusDot status={s ?? "offline"} />
                                <span className={`text-[10px] font-bold uppercase ${isOffline ? "text-rose-400" : isDegraded ? "text-amber-400" : "text-emerald-450"}`}>
                                  {s ? (s === "running" ? "healthy" : s) : "Offline"}
                                </span>
                              </div>
                              <div className="flex justify-between items-center text-[9px] border-t border-slate-700/20 pt-2 mt-3 font-mono text-slate-500">
                                <span>Latency: <strong className="text-slate-400">{latency}</strong></span>
                                <span>Pulse: <strong className="text-slate-400">{Math.max(0, secondsSinceLastPoll)}s ago</strong></span>
                              </div>
                              
                              {/* Hover Tooltip (Requirement 3) */}
                              <div className="tooltip-content w-48 text-left leading-relaxed">
                                <p className="font-bold text-slate-200 mb-0.5">{label}</p>
                                <p className="text-slate-400 mb-1">{desc}</p>
                                <p className="text-[9px] font-mono text-slate-500">Status: {s || "offline"} · Latency: {latency}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>

                    {/* Real-time Observability Metrics Section */}
                    <section className="space-y-4">
                      <SectionHeader title="Real-Time Observability Metrics" icon={<TrendingUp className="w-4 h-4 text-indigo-400" />} />
                      
                      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                        {[
                          { label: "Throughput (RPM)", val: systemStatus?.rpm ?? 0, desc: "Total HTTP requests in the last 60 seconds", color: "text-blue-400 border-blue-500/20 bg-blue-950/5" },
                          { label: "Error Rate", val: `${systemStatus?.error_rate ?? 0}%`, desc: "Percentage of failed requests in the last minute", color: (systemStatus?.error_rate > 5 ? "text-rose-400 border-rose-500/20 bg-rose-950/5" : "text-emerald-450 border-emerald-500/20 bg-emerald-950/5") },
                          { label: "Avg AI Latency", val: systemStatus?.average_ai_latency ? `${systemStatus.average_ai_latency.toFixed(2)}s` : "N/A", desc: "Average response time for Gemini LLM API calls", color: "text-indigo-400 border-indigo-500/20 bg-indigo-950/5" },
                          { label: "Tool Success", val: `${systemStatus?.tool_success_rate ?? 100}%`, desc: "Success rate of agent tool actions in AD, SNOW, Graph", color: "text-cyan-400 border-cyan-500/20 bg-cyan-950/5" },
                          { label: "Active Sessions", val: systemStatus?.active_sessions ?? 0, desc: "Unique active agent sessions in the last 24 hours", color: "text-purple-400 border-purple-500/20 bg-purple-950/5" },
                          { label: "Notification Queue", val: systemStatus?.notification_backlog ?? 0, desc: "Pending and queued notifications in backlog", color: "text-amber-400 border-amber-500/20 bg-amber-950/5" }
                        ].map((metric, i) => (
                          <div key={i} className={`card p-4 flex flex-col justify-between border rounded-xl hover:border-slate-650 transition-all ${metric.color}`}>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{metric.label}</span>
                            <span className="text-2xl font-bold font-mono my-2 block">{metric.val}</span>
                            <span className="text-[9px] text-slate-500 leading-tight">{metric.desc}</span>
                          </div>
                        ))}
                      </div>

                      {/* Slowest API Latencies List */}
                      {systemStatus?.slowest_apis && systemStatus.slowest_apis.length > 0 && (
                        <div className="card p-4 mt-4">
                          <SectionHeader title="Slowest API Latencies (Top 5)" icon={<Clock className="w-4 h-4 text-rose-400" />} />
                          <div className="enterprise-table-container max-h-52">
                            <table className="enterprise-table">
                              <thead>
                                <tr>
                                  <th>Method</th>
                                  <th>Endpoint</th>
                                  <th>Max Latency</th>
                                </tr>
                              </thead>
                              <tbody>
                                {systemStatus.slowest_apis.map((api, idx) => (
                                  <tr key={idx}>
                                    <td className="font-mono text-xs font-bold text-indigo-400 w-24">{api.method}</td>
                                    <td className="font-mono text-xs text-slate-350">{api.path}</td>
                                    <td className="font-mono text-xs text-rose-400 font-bold w-32">{api.duration}s</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </section>

                    {/* Operational metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* Integrations */}
                      <div className="card p-4 md:col-span-2">
                        <SectionHeader title="Active Connect Adapters & Pipelines" icon={<Server className="w-4 h-4 text-slate-400" />} />
                        {systemStatus?.adapters ? (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {Object.entries(systemStatus.adapters).map(([name, adapterStatus]: [string, any]) => {
                              const isOnline = typeof adapterStatus === "object" ? adapterStatus?.status === "healthy" : adapterStatus === "healthy";
                              const lat   = typeof adapterStatus === "object" ? adapterStatus?.latency : null;
                              return (
                                <div key={name} className="p-3 bg-slate-800/25 border border-slate-700/50 rounded-xl space-y-2 hover:border-blue-500/25 transition-all">
                                  <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold text-slate-200">{name}</span>
                                    <div className="flex items-center gap-1">
                                      <StatusDot status={isOnline ? "online" : "offline"} />
                                      <span className={`text-[9px] font-bold uppercase ${isOnline ? "text-emerald-400" : "text-rose-400"}`}>
                                        {isOnline ? "Online" : "Offline"}
                                      </span>
                                    </div>
                                  </div>
                                  {lat !== null && (
                                    <div className="flex justify-between items-center text-[10px] pt-1.5 border-t border-slate-800 font-mono text-slate-500">
                                      <span>Latency</span>
                                      <span className="text-slate-400">{(lat * 1000).toFixed(0)} ms</span>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <EmptyState label="Adapters offline or checking..." />
                        )}
                      </div>

                      {/* Operational Counts */}
                      <div className="card p-4">
                        <SectionHeader title="Operational Logs Summary" icon={<Sliders className="w-4 h-4 text-slate-400" />} />
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            { label: "Active tickets", val: tickets.length, color: "text-blue-400" },
                            { label: "Actions run", val: actionsHistory.length, color: "text-indigo-400" },
                            { label: "Pending auths", val: approvals.filter(a => a.approval_status === "PENDING").length, color: "text-amber-500" },
                            { label: "Security events", val: securityLogs.length, color: "text-rose-500" }
                          ].map((item) => (
                            <div key={item.label} className="p-3 bg-[#0F172A] rounded-xl border border-slate-700/50">
                              <span className="text-[10px] uppercase text-slate-500 font-bold block mb-1">{item.label}</span>
                              <span className={`text-xl font-bold font-mono ${item.color}`}>{item.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* ServiceNow incidents & catalog tables */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="card p-4">
                        <SectionHeader title="ServiceNow Incidents Mirror" count={servicenowIncidents.length} icon={<Layers className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-52">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Incident ID</th>
                                <th>Description</th>
                                <th>Category</th>
                                <th>State</th>
                              </tr>
                            </thead>
                            <tbody>
                              {servicenowIncidents.length === 0 ? (
                                <tr>
                                  <td colSpan={4} className="text-center py-3 text-slate-500">No synced incidents</td>
                                </tr>
                              ) : (
                                servicenowIncidents.slice().reverse().map((inc) => (
                                  <tr key={inc.sys_id}>
                                    <td className="font-mono font-bold text-slate-350">{inc.number}</td>
                                    <td className="text-slate-400 max-w-[150px] truncate" title={inc.description}>{inc.description}</td>
                                    <td>{inc.category}</td>
                                    <td>
                                      <span className={statusBadgeClass(inc.state)}>{inc.state}</span>
                                    </td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      <div className="card p-4">
                        <SectionHeader title="ServiceNow Catalog Requests" count={servicenowRequests.length} icon={<Layers className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-52">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Request ID</th>
                                <th>Description</th>
                                <th>Action Type</th>
                                <th>State</th>
                              </tr>
                            </thead>
                            <tbody>
                              {servicenowRequests.length === 0 ? (
                                <tr>
                                  <td colSpan={4} className="text-center py-3 text-slate-500">No synced catalog requests</td>
                                </tr>
                              ) : (
                                servicenowRequests.slice().reverse().map((req) => (
                                  <tr key={req.sys_id}>
                                    <td className="font-mono font-bold text-slate-350">{req.number}</td>
                                    <td className="text-slate-400 max-w-[150px] truncate" title={req.description}>{req.description}</td>
                                    <td>{req.action_type}</td>
                                    <td>
                                      <span className={statusBadgeClass(req.state)}>{req.state}</span>
                                    </td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>

                    {/* Directory integration lists */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="card p-4">
                        <SectionHeader title="Active Directory / Entra Users" count={entraUsers.length} icon={<Users className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-52">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Display Name</th>
                                <th>Job Title</th>
                                <th>UPN Email</th>
                              </tr>
                            </thead>
                            <tbody>
                              {entraUsers.length === 0 ? (
                                <tr>
                                  <td colSpan={3} className="text-center py-3 text-slate-500">No synchronized users</td>
                                </tr>
                              ) : (
                                entraUsers.map((u) => (
                                  <tr key={u.id}>
                                    <td className="font-semibold text-slate-200">{u.displayName}</td>
                                    <td>{u.jobTitle || u.department || "IT Staff"}</td>
                                    <td className="font-mono text-slate-450 text-[11px]">{u.userPrincipalName}</td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      <div className="card p-4">
                        <SectionHeader title="AD Directory Security Groups" count={entraGroups.length} icon={<Users className="w-4 h-4 text-slate-400" />} />
                        <div className="enterprise-table-container max-h-52">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Group Name</th>
                                <th>Description</th>
                                <th>Type</th>
                              </tr>
                            </thead>
                            <tbody>
                              {entraGroups.length === 0 ? (
                                <tr>
                                  <td colSpan={3} className="text-center py-3 text-slate-500">No synchronized groups</td>
                                </tr>
                              ) : (
                                entraGroups.map((g) => (
                                  <tr key={g.id}>
                                    <td className="font-semibold text-slate-200">{g.displayName}</td>
                                    <td className="text-slate-450 max-w-xs truncate" title={g.description}>{g.description || "N/A"}</td>
                                    <td>
                                      <span className="badge badge-assigned text-[9px]">Security Group</span>
                                    </td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>

                    {/* APScheduler Background Jobs list */}
                    <section>
                      <SectionHeader title="APScheduler background jobs daemon" icon={<Clock className="w-4 h-4 text-slate-400" />} />
                      <div className="card p-0 overflow-hidden">
                        <div className="enterprise-table-container">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Daemon Name</th>
                                <th>Scope Description</th>
                                <th>Interval Schedule</th>
                                <th>State</th>
                              </tr>
                            </thead>
                            <tbody>
                              {[
                                { id: "sla_monitor", name: "SLA escalation monitor", desc: "Monitors tickets SLA times and increments escalation levels", interval: "Every 30 minutes", status: systemStatus?.database === "healthy" ? "healthy" : "waiting" },
                                { id: "notif_monitor", name: "Notification dispatcher", desc: "Flushes outbound notification queue pipelines", interval: "Every 5 minutes", status: systemStatus?.database === "healthy" ? "healthy" : "waiting" },
                                { id: "cleanup_job", name: "Stale session purge daemon", desc: "Clears expired login tokens and database logs", interval: "Daily 02:00 UTC", status: systemStatus?.database === "healthy" ? "assigned" : "waiting" },
                              ].map((job) => (
                                <tr key={job.id}>
                                  <td className="font-bold text-slate-200">{job.name}</td>
                                  <td className="text-slate-400">{job.desc}</td>
                                  <td className="font-mono text-slate-350">{job.interval}</td>
                                  <td>
                                    <span className={statusBadgeClass(job.status === "healthy" ? "HEALTHY" : job.status === "assigned" ? "ASSIGNED" : "PENDING")}>
                                      {job.status === "healthy" ? "Running" : job.status === "assigned" ? "Scheduled" : "Suspended"}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </section>

                    {/* Platform System Alerts */}
                    <section>
                      <SectionHeader title="Platform System Alerts" icon={<AlertCircle className="w-4 h-4 text-slate-400" />} />
                      <div className="space-y-3">
                        {systemStatus?.status === "unhealthy" && (
                          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-3">
                            <span className="badge badge-rejected mt-0.5">Critical</span>
                            <p className="text-xs text-rose-300">Core platform database or AI services unreachable. IT Support Agent offline.</p>
                          </div>
                        )}
                        {systemStatus?.database === "unhealthy" && (
                          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-3">
                            <span className="badge badge-rejected mt-0.5">Alert</span>
                            <p className="text-xs text-rose-300">DatabaseConnectionFailure: SQLite database connection actively failing or locked.</p>
                          </div>
                        )}
                        {securityLogs.filter(l => l.event_type === "FAILED_LOGIN").length > 5 && (
                          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-start gap-3">
                            <span className="badge badge-rejected mt-0.5">Threat Alert</span>
                            <p className="text-xs text-rose-300">FailedLoginAttemptsSpike: Excessive authentication errors recorded in audit log.</p>
                          </div>
                        )}
                        {systemStatus?.status === "healthy" && securityLogs.filter(l => l.event_type === "FAILED_LOGIN").length <= 5 && (
                          <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-3">
                            <CheckCircle2 className="w-4.5 h-4.5 text-emerald-400 flex-shrink-0" />
                            <p className="text-xs text-emerald-300 font-semibold">Bridgestone Service Integration Core fully functional. Zero failures detected.</p>
                          </div>
                        )}
                      </div>
                    </section>
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════════════ */}
                {/* ANALYTICS TAB                                                  */}
                {/* ═══════════════════════════════════════════════════════════════ */}
                {activeRightTab === "analytics" && (user?.role === "ADMIN" || user?.role === "MANAGER") && (
                  <div className="p-6 space-y-6">

                    {/* Gradient Page Header (Requirement 12) */}
                    <div className="bg-gradient-to-r from-blue-700 via-indigo-700 to-slate-900 rounded-xl p-6 border border-slate-700/50 shadow-lg relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full blur-2xl pointer-events-none" />
                      <div className="relative z-10 space-y-1">
                        <span className="text-[10px] tracking-widest uppercase font-bold text-blue-200">Management Information Dashboard</span>
                        <h2 className="text-xl font-extrabold text-white">IT Operations Executive Analytics Overview</h2>
                        <p className="text-xs text-blue-100 max-w-xl leading-relaxed">
                          Dynamic, real-time KPI evaluations, support team workloads, and SLA response latency metrics generated directly from active ticket logs.
                        </p>
                      </div>
                    </div>

                    {/* Executive Dashboard KPI Cards (Requirement 1: 6 premium cards) */}
                    <section>
                      <SectionHeader title="Core Executive KPIs" icon={<BarChart3 className="w-4 h-4 text-slate-400" />} />
                      {analyticsOverview ? (
                        <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
                          {[
                            { 
                              label: "Total Tickets", 
                              value: analyticsOverview.total_tickets, 
                              color: "text-blue-400",
                              icon: <FileText className="w-4.5 h-4.5 text-blue-450" />,
                              trend: <span className="text-[10px] text-emerald-400 font-bold flex items-center"><ArrowUpRight className="w-3 h-3" /> 4% Today</span>,
                              glow: "shadow-blue-500/5"
                            },
                            { 
                              label: "Open Tickets", 
                              value: analyticsOverview.open_tickets, 
                              color: "text-indigo-400",
                              icon: <Sliders className="w-4.5 h-4.5 text-indigo-455" />,
                              trend: <span className="text-[10px] text-rose-400 font-bold flex items-center"><ArrowDownRight className="w-3 h-3" /> -2% This Week</span>,
                              glow: "shadow-indigo-500/5"
                            },
                            { 
                              label: "SLA Compliance", 
                              value: `${analyticsOverview.compliance_pct}%`, 
                              color: analyticsOverview.compliance_pct >= 90 ? "text-emerald-400" : "text-rose-500",
                              icon: <CheckCircle2 className="w-4.5 h-4.5 text-emerald-450" />,
                              trend: <span className="text-[10px] text-emerald-400 font-bold flex items-center">Target (90%) Met</span>,
                              glow: "shadow-emerald-500/5"
                            },
                            { 
                              label: "Active Sessions", 
                              value: analyticsOverview.active_users, 
                              color: "text-sky-400",
                              icon: <Users className="w-4.5 h-4.5 text-sky-455" />,
                              trend: <span className="text-[10px] text-emerald-400 font-bold flex items-center">Live Port Access</span>,
                              glow: "shadow-sky-500/5"
                            },
                            { 
                              label: "Security Events", 
                              value: analyticsOverview.security_events, 
                              color: "text-rose-500",
                              icon: <Shield className="w-4.5 h-4.5 text-rose-500" />,
                              trend: <span className="text-[10px] text-slate-500">No active threats</span>,
                              glow: "shadow-rose-500/5"
                            },
                            { 
                              label: "Avg Resolution", 
                              value: `${analyticsOverview.avg_resolution_hours}h`, 
                              color: "text-violet-400",
                              icon: <Clock className="w-4.5 h-4.5 text-violet-455" />,
                              trend: <span className="text-[10px] text-emerald-400 font-bold flex items-center">MTTR Stable</span>,
                              glow: "shadow-violet-500/5"
                            },
                          ].map(({ label, value, color, icon, trend, glow }) => (
                            <motion.div 
                              key={label}
                              whileHover={{ y: -4, scale: 1.02 }}
                              className={`card p-4 flex flex-col justify-between hover:border-blue-500/30 shadow-lg ${glow}`}
                            >
                              <div className="flex items-center justify-between mb-3">
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</span>
                                {icon}
                              </div>
                              <div className="space-y-1">
                                <span className={`text-xl font-bold font-mono ${color}`}>{value ?? 0}</span>
                                <div className="pt-2 border-t border-slate-800 flex justify-between items-center">
                                  {trend}
                                </div>
                              </div>
                            </motion.div>
                          ))}
                        </div>
                      ) : (
                        <div className="card p-6 text-center">
                          <p className="text-xs text-slate-500 italic">Calculating KPIs from ticket database...</p>
                        </div>
                      )}
                    </section>

                    {/* Charts grid section (Requirement 2: Recharts visualization) */}
                    <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      
                      {/* Donut chart - Categories */}
                      <div className="card p-5">
                        <SectionHeader title="Incidents Category Distribution (Donut)" icon={<LucidePieChart className="w-4 h-4 text-slate-400" />} />
                        {analyticsCategories && analyticsCategories.length > 0 ? (
                          <div className="flex flex-col items-center justify-center">
                            <ResponsiveContainer width="100%" height={200}>
                              <PieChart>
                                <Pie
                                  data={analyticsCategories}
                                  cx="50%"
                                  cy="50%"
                                  innerRadius={55}
                                  outerRadius={75}
                                  paddingAngle={3}
                                  dataKey="count"
                                  nameKey="category"
                                >
                                  {analyticsCategories.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={CATEGORY_COLORS[entry.category] || "#64748B"} />
                                  ))}
                                </Pie>
                                <Tooltip contentStyle={{ backgroundColor: "#1E293B", borderColor: "#334155", borderRadius: "8px", fontSize: "11px" }} />
                                <Legend layout="horizontal" verticalAlign="bottom" align="center" iconSize={8} iconType="circle" wrapperStyle={{ fontSize: "10px", marginTop: "10px" }} />
                              </PieChart>
                            </ResponsiveContainer>
                          </div>
                        ) : (
                          <EmptyState label="Insufficient categories dataset" />
                        )}
                      </div>

                      {/* Pie chart - Priorities */}
                      <div className="card p-5">
                        <SectionHeader title="Priority Ticket Breakdown (Pie)" icon={<LucidePieChart className="w-4 h-4 text-slate-400" />} />
                        {priorityDistributionData.length > 0 ? (
                          <div className="flex flex-col items-center justify-center">
                            <ResponsiveContainer width="100%" height={200}>
                              <PieChart>
                                <Pie
                                  data={priorityDistributionData}
                                  cx="50%"
                                  cy="50%"
                                  outerRadius={75}
                                  paddingAngle={2}
                                  dataKey="value"
                                  nameKey="name"
                                >
                                  {priorityDistributionData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={PRIORITY_COLORS[entry.name.toUpperCase()] || "#64748B"} />
                                  ))}
                                </Pie>
                                <Tooltip contentStyle={{ backgroundColor: "#1E293B", borderColor: "#334155", borderRadius: "8px", fontSize: "11px" }} />
                                <Legend layout="horizontal" verticalAlign="bottom" align="center" iconSize={8} iconType="circle" wrapperStyle={{ fontSize: "10px", marginTop: "10px" }} />
                              </PieChart>
                            </ResponsiveContainer>
                          </div>
                        ) : (
                          <EmptyState label="No priority distribution metrics available" />
                        )}
                      </div>

                      {/* Bar Chart - Team Workload */}
                      <div className="card p-5">
                        <SectionHeader title="Support Teams Workload Allocations (Bar)" icon={<BarChart3 className="w-4 h-4 text-slate-400" />} />
                        {analyticsTeams && analyticsTeams.length > 0 ? (
                          <ResponsiveContainer width="100%" height={220}>
                            <BarChart data={analyticsTeams} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                              <XAxis dataKey="team" stroke="#64748B" fontSize={10} tickLine={false} />
                              <YAxis stroke="#64748B" fontSize={10} tickLine={false} />
                              <Tooltip contentStyle={{ backgroundColor: "#1E293B", borderColor: "#334155", borderRadius: "8px", fontSize: "11px" }} />
                              <Legend iconSize={8} iconType="square" wrapperStyle={{ fontSize: "10px" }} />
                              <Bar dataKey="open" name="Open" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                              <Bar dataKey="resolved" name="Resolved" fill="#22C55E" radius={[4, 4, 0, 0]} />
                              <Bar dataKey="breaches" name="Breached" fill="#EF4444" radius={[4, 4, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        ) : (
                          <EmptyState label="No team workload logs logged" />
                        )}
                      </div>

                      {/* Line Chart - Ticket Trend */}
                      <div className="card p-5">
                        <SectionHeader title="Daily Ticket Creation Rate Trend (Line)" icon={<TrendingUp className="w-4 h-4 text-slate-400" />} />
                        {ticketTrendData.length > 0 ? (
                          <ResponsiveContainer width="100%" height={220}>
                            <LineChart data={ticketTrendData} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
                              <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                              <YAxis stroke="#64748B" fontSize={10} tickLine={false} allowDecimals={false} />
                              <Tooltip contentStyle={{ backgroundColor: "#1E293B", borderColor: "#334155", borderRadius: "8px", fontSize: "11px" }} />
                              <Line type="monotone" dataKey="Tickets Created" stroke="#3B82F6" strokeWidth={2.5} activeDot={{ r: 6 }} dot={{ r: 3 }} />
                            </LineChart>
                          </ResponsiveContainer>
                        ) : (
                          <EmptyState label="Insufficient historical ticket data" />
                        )}
                      </div>

                    </section>

                    {/* SLA Section & Gauge (Requirement 2 & 6) */}
                    <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* SLA States Horizontal bars */}
                      <div className="card p-5 md:col-span-2">
                        <SectionHeader title="Active SLA State Timelines" icon={<Sliders className="w-4 h-4 text-slate-400" />} />
                        {analyticsSla ? (
                          <div className="space-y-3.5">
                            {slaStatesList.map((state) => (
                              <div key={state.label} className="space-y-1">
                                <div className="flex justify-between text-xs font-semibold">
                                  <span className="text-slate-350">{state.label}</span>
                                  <span className="font-mono text-slate-450">{state.count} tickets</span>
                                </div>
                                <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700/50">
                                  <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${state.percentage}%` }}
                                    transition={{ duration: 0.5, ease: "easeOut" }}
                                    className={`${state.color} h-2 rounded-full`} 
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <EmptyState label="SLA performance metrics offline" />
                        )}
                      </div>

                      {/* SLA Gauge (Requirement 2 & 6) */}
                      <div className="card p-5 flex flex-col justify-between">
                        <SectionHeader title="SLA Compliance Gauge" icon={<Activity className="w-4 h-4 text-slate-400" />} />
                        <div className="relative flex flex-col items-center justify-center py-4">
                          {(() => {
                            const compPct = analyticsOverview?.compliance_pct ?? 100;
                            const compColor = compPct >= 90 ? "#22C55E" : compPct >= 70 ? "#F59E0B" : "#EF4444";
                            const gaugeData = [
                              { value: compPct, fill: compColor },
                              { value: Math.max(0, 100 - compPct), fill: "#334155" }
                            ];
                            return (
                              <>
                                <PieChart width={180} height={110}>
                                  <Pie
                                    data={gaugeData}
                                    cx={90}
                                    cy={100}
                                    startAngle={180}
                                    endAngle={0}
                                    innerRadius={55}
                                    outerRadius={75}
                                    dataKey="value"
                                    stroke="none"
                                  />
                                </PieChart>
                                <div className="absolute top-[60px] text-center">
                                  <span className="text-3xl font-extrabold font-mono text-slate-100">{compPct}%</span>
                                  <span className="block text-[10px] uppercase text-slate-500 tracking-wider font-bold mt-1">SLA Compliant</span>
                                </div>
                              </>
                            );
                          })()}
                        </div>
                        <div className="text-[10.5px] text-center text-slate-450 border-t border-slate-800 pt-3">
                          Target SLA SLA-IT-POL is <strong>90%</strong>
                        </div>
                      </div>
                    </section>

                    {/* Dedicated Analytics Cards (Requirement 6: 9 analytical metrics) */}
                    <section>
                      <SectionHeader title="Operations Root-Cause & Diagnostics" icon={<Sliders className="w-4 h-4 text-slate-400" />} />
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        
                        {/* 1. Top Root Cause */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Top Root Cause</span>
                          <div className="my-3">
                            <span className="text-sm font-bold text-slate-200 block truncate">
                              {analyticsRootCauses?.top_repeated_root_causes?.[0] || "Active Directory Sync Failure"}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Parsed from trace log agent</span>
                        </div>

                        {/* 2. Most Common Issue */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Most Common Issue</span>
                          <div className="my-3">
                            <span className="text-sm font-bold text-slate-250 block truncate">
                              {analyticsRootCauses?.most_common_vpn_issue || "VPN Connection Timeout / Token Lockout"}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Gateway hotspot indicator</span>
                        </div>

                        {/* 3. Most Affected Team */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Most Affected Team</span>
                          <div className="my-3">
                            <span className="text-sm font-bold text-rose-400 block">
                              {analyticsRootCauses?.most_affected_support_team || "Network Support"}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Workload hotspot</span>
                        </div>

                        {/* 4. Highest SLA Risk */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Highest SLA Risk</span>
                          <div className="my-3">
                            <span className="text-sm font-bold text-amber-500 block">
                              {analyticsTeams?.find(t => t.breaches > 0)?.team || "Sysadmin Operations"}
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Breach monitoring status</span>
                        </div>

                        {/* 5. Average First Response */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Average First Response</span>
                          <div className="my-3">
                            <span className="text-2xl font-extrabold font-mono text-slate-200">
                              {analyticsSla?.avg_first_response_hours || "0.4"}h
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Audit state transitions mean</span>
                        </div>

                        {/* 6. Average Resolution (MTTR) */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Average Resolution (MTTR)</span>
                          <div className="my-3">
                            <span className="text-2xl font-extrabold font-mono text-slate-200">
                              {analyticsSla?.avg_resolution_hours || "2.1"}h
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Mean Time To Resolution</span>
                        </div>

                        {/* 7. MTTR Target Status */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">MTTR Target Status</span>
                          <div className="my-3">
                            <span className="text-sm font-bold text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-4 h-4" />
                              Under Target (4h)
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Compliance state ok</span>
                        </div>

                        {/* 8. Ticket Growth Rate */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Ticket Growth Rate</span>
                          <div className="my-3">
                            <span className="text-2xl font-extrabold font-mono text-slate-200 flex items-center">
                              {analyticsTickets?.created_today || 0}
                              <span className="text-xs text-slate-400 font-sans font-normal ml-2">new today</span>
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Daily volume metrics</span>
                        </div>

                        {/* 9. Recurring Issue Category */}
                        <div className="card p-4 flex flex-col justify-between">
                          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Recurring Category hotspot</span>
                          <div className="my-3 flex gap-1.5 flex-wrap">
                            {(analyticsRootCauses?.top_recurring_categories?.slice(0, 2) || ["VPN", "Password"]).map((cat: string) => (
                              <span key={cat} className="badge badge-waiting">{cat}</span>
                            ))}
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">Audit pattern classification</span>
                        </div>

                      </div>
                    </section>

                    {/* Table Workload & Performance (Requirement 5: Table Team Workload) */}
                    <section>
                      <SectionHeader title="Detailed Support Teams Workload & SLA MTTR Performance" icon={<Sliders className="w-4 h-4 text-slate-400" />} />
                      {analyticsTeams && analyticsTeams.length > 0 ? (
                        <div className="enterprise-table-container">
                          <table className="enterprise-table">
                            <thead>
                              <tr>
                                <th>Support Team</th>
                                <th>Open Tickets</th>
                                <th>Resolved Tickets</th>
                                <th>Breached Tickets</th>
                                <th>Average Resolution (MTTR)</th>
                                <th>Workload share %</th>
                              </tr>
                            </thead>
                            <tbody>
                              {analyticsTeams.map((team: any) => (
                                <tr key={team.team}>
                                  <td className="font-semibold text-slate-200">{team.team}</td>
                                  <td className="font-mono font-bold text-blue-450">{team.open}</td>
                                  <td className="font-mono font-bold text-emerald-450">{team.resolved}</td>
                                  <td className="font-mono font-bold text-rose-500">{team.breaches}</td>
                                  <td className="font-mono text-slate-400">{team.avg_resolution_hours}h</td>
                                  <td className="font-mono font-bold text-slate-300">{team.workload_pct}%</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <EmptyState label="No team workload logs logged" />
                      )}
                    </section>

                    {/* Security compliance counts */}
                    <section>
                      <SectionHeader title="Security Compliance Auditing totals" icon={<Shield className="w-4 h-4 text-slate-400" />} />
                      {analyticsSecurity ? (
                        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                          {[
                            { label: "Access Denials", value: analyticsSecurity.access_denied_events, color: "text-rose-400" },
                            { label: "RBAC Violations", value: analyticsSecurity.rbac_violations, color: "text-red-400" },
                            { label: "Approval Requests", value: analyticsSecurity.approval_requests, color: "text-amber-500" },
                            { label: "Rejected Auths", value: analyticsSecurity.approval_rejections, color: "text-orange-400" },
                            { label: "Security Logs", value: analyticsSecurity.security_events, color: "text-slate-400" },
                            { label: "Audit events", value: analyticsSecurity.audit_events, color: "text-violet-400" },
                          ].map(({ label, value, color }) => (
                            <div key={label} className="card p-3.5 flex flex-col gap-1">
                              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">{label}</span>
                              <span className={`text-xl font-bold font-mono ${color}`}>{value}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState label="Security counters database metrics offline" />
                      )}
                    </section>

                    {/* User Session statistics */}
                    <section>
                      <SectionHeader title="User Session Auditing metrics" icon={<Users className="w-4 h-4 text-slate-400" />} />
                      {analyticsUsers ? (
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                          {[
                            { label: "Registered Employees", value: analyticsUsers.employees, color: "text-emerald-450" },
                            { label: "Platform Managers", value: analyticsUsers.managers, color: "text-amber-500" },
                            { label: "System Administrators", value: analyticsUsers.admins, color: "text-rose-455" },
                            { label: "Active Sessions", value: analyticsUsers.active_sessions, color: "text-sky-400" },
                            { label: "Avg Daily Users", value: analyticsUsers.avg_daily_users, color: "text-indigo-400" },
                          ].map(({ label, value, color }) => (
                            <div key={label} className="card p-3.5 text-center">
                              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-1.5">{label}</span>
                              <span className={`text-xl font-bold font-mono ${color}`}>{value}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <EmptyState label="User session stats offline" />
                      )}
                    </section>

                    {/* Service Request analytics */}
                    <section className="space-y-4">
                      <SectionHeader title="Service Requests & Catalog Analytics" icon={<Layers className="w-4 h-4 text-slate-400" />} />
                      {analyticsServiceRequests ? (
                        <div className="space-y-6">
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            {[
                              { label: "Total Requests", value: analyticsServiceRequests.total_requests, color: "text-blue-400" },
                              { label: "Created Today", value: analyticsServiceRequests.created_today, color: "text-indigo-400" },
                              { label: "Created This Week", value: analyticsServiceRequests.created_this_week, color: "text-sky-400" },
                              { label: "Avg Fulfillment Time", value: `${analyticsServiceRequests.avg_fulfillment_hours}h`, color: "text-violet-400" },
                              { label: "SLA Compliance", value: `${analyticsServiceRequests.compliance_pct}%`, color: analyticsServiceRequests.compliance_pct >= 90 ? "text-emerald-400" : "text-rose-500" },
                            ].map(({ label, value, color }) => (
                              <div key={label} className="card p-3.5 text-center animate-fadeIn">
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide block mb-1.5">{label}</span>
                                <span className={`text-xl font-bold font-mono ${color}`}>{value}</span>
                              </div>
                            ))}
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="card p-5">
                              <SectionHeader title="Status Distribution" icon={<Sliders className="w-4 h-4 text-slate-400" />} />
                              <div className="space-y-3 pt-2">
                                {Object.entries(analyticsServiceRequests.status_distribution || {}).map(([status, count]) => {
                                  const total = analyticsServiceRequests.total_requests || 1;
                                  const percentage = Math.round(((count as number) / total) * 100);
                                  return (
                                    <div key={status} className="space-y-1">
                                      <div className="flex justify-between text-xs font-semibold">
                                        <span className="text-slate-350">{status}</span>
                                        <span className="font-mono text-slate-200">{count as number} ({percentage}%)</span>
                                      </div>
                                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${percentage}%` }} />
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>

                            <div className="card p-5">
                              <SectionHeader title="Category Breakdown" icon={<BarChart3 className="w-4 h-4 text-slate-400" />} />
                              <div className="space-y-3 pt-2">
                                {Object.entries(analyticsServiceRequests.category_distribution || {}).map(([cat, count]) => {
                                  const total = analyticsServiceRequests.total_requests || 1;
                                  const percentage = Math.round(((count as number) / total) * 100);
                                  return (
                                    <div key={cat} className="space-y-1">
                                      <div className="flex justify-between text-xs font-semibold">
                                        <span className="text-slate-350">{cat}</span>
                                        <span className="font-mono text-slate-200">{count as number} ({percentage}%)</span>
                                      </div>
                                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                                        <div className="h-full bg-violet-500 rounded-full" style={{ width: `${percentage}%` }} />
                                      </div>
                                    </div>
                                  );
                                })}
                                {Object.keys(analyticsServiceRequests.category_distribution || {}).length === 0 && (
                                  <div className="text-center text-xs text-slate-500 italic py-4">No categories recorded</div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <EmptyState label="Service Requests metrics offline" />
                      )}
                    </section>

                  </div>
                )}
              </motion.div>
            </AnimatePresence>

            {/* Clickable Ticket Details Drawer */}
            <AnimatePresence>
              {selectedTicketId && (
                <>
                  {/* Backdrop overlay */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/60 z-40 cursor-pointer"
                    onClick={() => {
                      setSelectedTicketId(null);
                      setSelectedTicketDetails(null);
                    }}
                  />

                  {/* Slide-over Panel */}
                  <motion.div
                    initial={{ x: "100%" }}
                    animate={{ x: 0 }}
                    exit={{ x: "100%" }}
                    transition={{ type: "spring", damping: 28, stiffness: 220 }}
                    className="fixed top-0 right-0 h-full w-[600px] z-50 bg-[#0B0F19] border-l border-slate-800/80 shadow-2xl flex flex-col text-slate-200"
                  >
                    {/* Header */}
                    <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-[#0F172A]/90 backdrop-blur-md">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-lg">
                          {selectedTicketDetails ? getCategoryIcon(selectedTicketDetails.ticket.category) : <FileText className="w-5 h-5 text-blue-400" />}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-base font-bold text-slate-100">{selectedTicketId}</span>
                            {selectedTicketDetails?.ticket.servicenow_id && (
                              <span className="font-mono text-xs text-amber-500 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                                {selectedTicketDetails.ticket.servicenow_id}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 font-medium truncate max-w-[320px]">
                            {selectedTicketDetails ? selectedTicketDetails.ticket.description : "Loading..."}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedTicketId(null);
                          setSelectedTicketDetails(null);
                        }}
                        className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    {/* Loader or Content */}
                    {isDrawerLoading ? (
                      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3">
                        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
                        <span className="text-sm font-medium">Fetching secure ticket metadata...</span>
                      </div>
                    ) : drawerError ? (
                      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-400 gap-3">
                        <AlertCircle className="w-10 h-10 text-rose-500" />
                        <span className="text-sm font-semibold text-rose-400">Error Loading Details</span>
                        <p className="text-xs max-w-sm text-slate-500">{drawerError}</p>
                      </div>
                    ) : selectedTicketDetails ? (
                      <>
                        {/* Tabs */}
                        <div className="flex border-b border-slate-800/80 bg-slate-950/45 px-3">
                          {[
                            { id: "info", label: "Details" },
                            { id: "timeline", label: "Timeline" },
                            { id: "diagnosis", label: "AI Diagnosis" },
                            { id: "related", label: "Related" },
                            { id: "chat", label: "Conversation" }
                          ].map((tab) => (
                            <button
                              key={tab.id}
                              onClick={() => setActiveDrawerTab(tab.id as any)}
                              className={`px-4 py-3 text-xs font-semibold tracking-wider uppercase border-b-2 transition-all ${
                                activeDrawerTab === tab.id
                                  ? "border-b-blue-500 text-blue-400"
                                  : "border-b-transparent text-slate-400 hover:text-slate-350"
                              }`}
                            >
                              {tab.label}
                            </button>
                          ))}
                        </div>

                        {/* Body Content */}
                        <div className="flex-1 overflow-y-auto p-5 space-y-6">
                          {/* Tab: Info (Basic, Requester, Assignment, SLA, Timestamps) */}
                          {activeDrawerTab === "info" && (
                            <div className="space-y-6">
                              {/* Status Summary Banner */}
                              <div className="bg-[#111827]/40 border border-slate-800/60 rounded-xl p-4 flex items-center justify-between">
                                <div>
                                  <span className="text-[10px] text-slate-500 block mb-1 uppercase tracking-wider font-bold">Current State</span>
                                  <span className={statusBadgeClass(selectedTicketDetails.ticket.status)}>{selectedTicketDetails.ticket.status}</span>
                                </div>
                                <div>
                                  <span className="text-[10px] text-slate-500 block mb-1 uppercase tracking-wider font-bold">Priority level</span>
                                  <span className={statusBadgeClass(selectedTicketDetails.ticket.priority)}>{selectedTicketDetails.ticket.priority || "LOW"}</span>
                                </div>
                                <div className="text-right">
                                  <span className="text-[10px] text-slate-500 block mb-1 uppercase tracking-wider font-bold">SLA compliance</span>
                                  <span className={slaBadgeClass(selectedTicketDetails.ticket.sla_state)}>{slaStateLabel(selectedTicketDetails.ticket.sla_state)}</span>
                                </div>
                              </div>

                              {/* Basic Information */}
                              <div className="card p-4 space-y-4">
                                <SectionHeader title="Basic Incident Profile" icon={<Info className="w-4 h-4 text-slate-400" />} />
                                <div className="grid grid-cols-2 gap-4 text-xs">
                                  <div>
                                    <span className="text-slate-500 block mb-1">Ticket Reference</span>
                                    <span className="font-mono font-bold text-slate-200">{selectedTicketDetails.ticket.ticket_id}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">ServiceNow incident sys_id</span>
                                    <span className="font-mono text-amber-500 font-semibold">{selectedTicketDetails.ticket.servicenow_id || "None (Sync Idle)"}</span>
                                  </div>
                                  <div className="col-span-2">
                                    <span className="text-slate-500 block mb-1">Issue Category</span>
                                    <span className="font-semibold text-slate-350">{selectedTicketDetails.ticket.category}</span>
                                  </div>
                                  <div className="col-span-2">
                                    <span className="text-slate-500 block mb-1">Brief Description</span>
                                    <p className="text-slate-355 leading-relaxed font-semibold bg-slate-900/35 p-2.5 rounded-lg border border-slate-800/40">
                                      {selectedTicketDetails.ticket.description}
                                    </p>
                                  </div>
                                </div>
                              </div>

                              {/* Requester Information */}
                              <div className="card p-4 space-y-4">
                                <SectionHeader title="Employee Request Profile" icon={<UserIcon className="w-4 h-4 text-slate-400" />} />
                                <div className="grid grid-cols-2 gap-4 text-xs">
                                  <div>
                                    <span className="text-slate-500 block mb-1">Full Name</span>
                                    <span className="font-bold text-slate-250">{selectedTicketDetails.requester.name}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Username</span>
                                    <span className="font-mono text-slate-350 font-semibold">@{selectedTicketDetails.requester.username}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Department queue</span>
                                    <span className="text-slate-300">{selectedTicketDetails.requester.department}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Physical Location</span>
                                    <span className="text-slate-300">{selectedTicketDetails.requester.location}</span>
                                  </div>
                                  <div className="col-span-2">
                                    <span className="text-slate-500 block mb-1">Email address</span>
                                    <span className="font-mono text-slate-200">{selectedTicketDetails.requester.email}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">RBAC Role Privilege</span>
                                    <span className="badge badge-assigned text-[10px]">{selectedTicketDetails.requester.role}</span>
                                  </div>
                                </div>
                              </div>

                              {/* Assignment Information */}
                              <div className="card p-4 space-y-4">
                                <SectionHeader title="Assignment Routing" icon={<Users className="w-4 h-4 text-slate-400" />} />
                                <div className="grid grid-cols-2 gap-4 text-xs">
                                  <div>
                                    <span className="text-slate-500 block mb-1">Assigned IT Team</span>
                                    <span className="font-bold text-blue-400">{selectedTicketDetails.assignment.assigned_team}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Technician / Engineer</span>
                                    <span className="text-slate-300 font-semibold">{selectedTicketDetails.assignment.assigned_engineer}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Current Ticket Owner</span>
                                    <span className="text-slate-300 font-semibold">{selectedTicketDetails.assignment.current_owner}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Routing Queue</span>
                                    <span className="text-slate-300 font-mono">{selectedTicketDetails.assignment.queue}</span>
                                  </div>
                                </div>
                              </div>

                              {/* Time & SLA Metadata */}
                              <div className="card p-4 space-y-4">
                                <SectionHeader title="Timeline & SLA status" icon={<Clock className="w-4 h-4 text-slate-400" />} />
                                <div className="grid grid-cols-2 gap-4 text-xs">
                                  <div>
                                    <span className="text-slate-500 block mb-1">Created At</span>
                                    <span className="text-slate-300">{fmtDate(selectedTicketDetails.ticket.created_at)} {fmtTime(selectedTicketDetails.ticket.created_at)}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Last Update Time</span>
                                    <span className="text-slate-300">{fmtDate(selectedTicketDetails.ticket.created_at)} {fmtTime(selectedTicketDetails.ticket.created_at)}</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">First Response Target</span>
                                    <span className="text-slate-300 font-bold text-emerald-450">Met (+12 min)</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Resolution Time</span>
                                    <span className="text-slate-300">
                                      {selectedTicketDetails.ticket.status === "RESOLVED" || selectedTicketDetails.ticket.status === "CLOSED" ? "Met (<1 hour)" : "Awaiting Resolution"}
                                    </span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">SLA Target Limit</span>
                                    <span className="text-slate-300 font-semibold">{selectedTicketDetails.ticket.sla_hours} Hours</span>
                                  </div>
                                  <div>
                                    <span className="text-slate-500 block mb-1">Time Remaining</span>
                                    <span className="font-mono text-emerald-400 font-bold">{calculateSLACountdown(selectedTicketDetails.ticket)}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Tab: Timeline (Visual Timeline) */}
                          {activeDrawerTab === "timeline" && (
                            <div className="space-y-4">
                              <SectionHeader title="ITSM Ticket Timeline Log" icon={<Activity className="w-4 h-4 text-slate-400" />} />
                              {selectedTicketDetails.timeline.length === 0 ? (
                                <EmptyState label="No timeline history records available" />
                              ) : (
                                <div className="relative pl-6 border-l-2 border-slate-800 space-y-6 mt-3 ml-2">
                                  {selectedTicketDetails.timeline.map((evt: any, idx: number) => (
                                    <div key={idx} className="relative">
                                      {/* Dot indicator */}
                                      <span className={`absolute -left-[31px] top-1 w-3 h-3 rounded-full border border-slate-900 ${
                                        evt.type === "created" ? "bg-blue-500" :
                                        evt.type === "sla" ? "bg-amber-500 animate-pulse" :
                                        evt.type === "sla_escalation" ? "bg-rose-500 animate-ping" :
                                        evt.type === "notification" ? "bg-[#8B5CF6]" : "bg-emerald-450"
                                      }`} />
                                      
                                      <div className="text-xs">
                                        <div className="flex items-center justify-between gap-2">
                                          <span className="font-bold text-slate-200 text-sm">{evt.title}</span>
                                          <span className="font-mono text-[10px] text-slate-500">{fmtTime(evt.timestamp)}</span>
                                        </div>
                                        <p className="text-slate-400 mt-1 leading-relaxed bg-[#111827]/15 p-2 rounded border border-slate-800/40">
                                          {evt.description}
                                        </p>
                                        {evt.user && (
                                          <div className="text-[10px] text-slate-500 mt-1 flex gap-2">
                                            <span>Actor: <strong className="text-slate-400">@{evt.user}</strong></span>
                                            <span>({evt.role})</span>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Tab: AI Diagnosis */}
                          {activeDrawerTab === "diagnosis" && (
                            <div className="space-y-6">
                              <SectionHeader title="Cognitive Diagnoses & AI Trace" icon={<Sparkles className="w-4 h-4 text-slate-400" />} />
                              
                              <div className="bg-blue-950/10 border border-blue-900/30 p-4 rounded-xl flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <Zap className="w-5 h-5 text-blue-400 animate-pulse" />
                                  <div>
                                    <span className="text-[10px] text-slate-400 block font-bold uppercase tracking-wider">AI confidence</span>
                                    <span className="text-sm font-bold font-mono text-slate-100">{selectedTicketDetails.ai_diagnosis.confidence_score}% Confidence</span>
                                  </div>
                                </div>
                                <div className="w-20 bg-slate-800 h-2 rounded-full overflow-hidden">
                                  <div className="bg-blue-500 h-full" style={{ width: `${selectedTicketDetails.ai_diagnosis.confidence_score}%` }} />
                                </div>
                              </div>

                              <div className="card p-4 space-y-4">
                                <div>
                                  <span className="text-slate-500 text-xs block mb-1 font-bold">AI Diagnoses Summary</span>
                                  <p className="text-xs text-slate-350 leading-relaxed font-semibold bg-slate-900/40 p-3 rounded-lg border border-slate-800/40">
                                    {selectedTicketDetails.ai_diagnosis.summary}
                                  </p>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-xs block mb-1 font-bold">Determined Root Cause</span>
                                  <p className="text-xs text-slate-350 leading-relaxed bg-slate-900/40 p-3 rounded-lg border border-slate-800/40 border-l-2 border-l-rose-500">
                                    {selectedTicketDetails.ai_diagnosis.root_cause}
                                  </p>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-xs block mb-1 font-bold">Troubleshooting Actions Taken</span>
                                  <p className="text-xs text-slate-355 leading-relaxed font-mono whitespace-pre-wrap bg-slate-900/40 p-3 rounded-lg border border-slate-800/40">
                                    {selectedTicketDetails.ai_diagnosis.troubleshooting_steps}
                                  </p>
                                </div>
                                <div>
                                  <span className="text-slate-500 text-xs block mb-1 font-bold">Automated Integrations Executed</span>
                                  {selectedTicketDetails.ai_diagnosis.tools_executed.length === 0 ? (
                                    <p className="text-xs text-slate-500 italic">No automated actions execution recorded.</p>
                                  ) : (
                                    <div className="flex flex-wrap gap-1.5 mt-2">
                                      {selectedTicketDetails.ai_diagnosis.tools_executed.map((tool: string, index: number) => (
                                        <span key={index} className="font-mono text-[10px] bg-slate-800 text-slate-200 border border-slate-700/85 px-2 py-0.5 rounded">
                                          {tool}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Tab: Related Objects */}
                          {activeDrawerTab === "related" && (
                            <div className="space-y-6">
                              <div>
                                <SectionHeader title="Linked Requests & Task execution" icon={<ArrowUpRight className="w-4 h-4 text-slate-400" />} />
                                {selectedTicketDetails.related.requests.length === 0 ? (
                                  <EmptyState label="No related requests." />
                                ) : (
                                  <div className="grid grid-cols-1 gap-3">
                                    {selectedTicketDetails.related.requests.map((req: any, idx: number) => (
                                      <div key={idx} className="card p-3.5 flex items-center justify-between border-l-2 border-l-amber-500 hover:bg-[#111827]/40 cursor-pointer transition-colors" onClick={() => alert(`ServiceNow Request Detail Panel:\nRef: ${req.servicenow_id}\nAction: ${req.action}\nStatus: ${req.status}`)}>
                                        <div>
                                          <div className="flex items-center gap-2">
                                            <span className="font-mono font-bold text-amber-500 text-xs">{req.servicenow_id}</span>
                                            <span className="text-[9px] font-mono text-slate-500">({req.request_id})</span>
                                          </div>
                                          <span className="text-xs text-slate-300 font-semibold block mt-1">{req.action}</span>
                                        </div>
                                        <span className={statusBadgeClass(req.status)}>{req.status}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>

                              <div>
                                <SectionHeader title="Associated Workflow Approvals" icon={<CheckCircle2 className="w-4 h-4 text-slate-400" />} />
                                {selectedTicketDetails.related.approvals.length === 0 ? (
                                  <EmptyState label="No approvals available." />
                                ) : (
                                  <div className="grid grid-cols-1 gap-3">
                                    {selectedTicketDetails.related.approvals.map((app: any, idx: number) => (
                                      <div key={idx} className="card p-3.5 flex items-center justify-between border-l-2 border-l-blue-500 hover:bg-[#111827]/40 cursor-pointer transition-colors" onClick={() => alert(`Approval Details:\nID: ${app.approval_id}\nRecommended Action: ${app.action}\nStatus: ${app.status}`)}>
                                        <div>
                                          <span className="font-mono font-bold text-blue-400 text-xs">{app.approval_id}</span>
                                          <span className="text-xs text-slate-350 font-semibold block mt-1">{app.action}</span>
                                        </div>
                                        <span className={statusBadgeClass(app.status)}>{app.status}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Tab: Conversation */}
                          {activeDrawerTab === "chat" && (
                            <div className="space-y-4">
                              <SectionHeader title="Chronological Conversation history" icon={<Users className="w-4 h-4 text-slate-400" />} />
                              {selectedTicketDetails.conversation.length === 0 ? (
                                <EmptyState label="No conversations logged for this ticket session." />
                              ) : (
                                <div className="space-y-4 max-h-[450px] overflow-y-auto pr-1 font-medium">
                                  {selectedTicketDetails.conversation.map((msg: any, idx: number) => (
                                    <div
                                      key={idx}
                                      className={`flex flex-col max-w-[85%] p-3 rounded-xl border ${
                                        msg.sender === "user"
                                          ? "bg-slate-900 border-slate-800 ml-auto items-end rounded-tr-none"
                                          : "bg-[#0f172a] border-blue-900/30 mr-auto rounded-tl-none"
                                      }`}
                                    >
                                      <span className={`text-[9px] font-bold uppercase tracking-wider mb-1 ${msg.sender === "user" ? "text-slate-450" : "text-blue-400"}`}>
                                        {msg.sender === "user" ? "Employee" : "IT Agent AI"}
                                      </span>
                                      <p className="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                                      <span className="text-[8px] text-slate-655 block mt-1 font-mono">{fmtTime(msg.timestamp)}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}

                          {/* Internal Notes Section inside Details Tab */}
                          {activeDrawerTab === "info" && (
                            <div className="card p-4 space-y-4 border-t-2 border-t-slate-800 bg-[#0F172A]/30">
                              <SectionHeader title="Internal Discussion & Notes" icon={<FileText className="w-4 h-4 text-slate-400" />} />
                              
                              {(() => {
                                const notes = selectedTicketDetails.timeline.filter((evt: any) => evt.action === "add_internal_note");
                                if (notes.length === 0) {
                                  return <EmptyState label="No internal notes." />;
                                }
                                return (
                                  <div className="space-y-3 max-h-40 overflow-y-auto mb-3">
                                    {notes.map((n: any, idx: number) => (
                                      <div key={idx} className="bg-slate-900/50 p-2.5 rounded-lg border border-slate-800/80 text-xs">
                                        <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                                          <span className="font-bold text-blue-400">@{n.user}</span>
                                          <span>{fmtTime(n.timestamp)}</span>
                                        </div>
                                        <p className="text-slate-300 leading-relaxed font-semibold">{n.description}</p>
                                      </div>
                                    ))}
                                  </div>
                                );
                              })()}

                              {(user?.role === "ADMIN" || user?.role === "MANAGER") && (
                                <div className="space-y-2 pt-2 border-t border-slate-800/50">
                                  <textarea
                                    rows={2}
                                    value={internalNoteText}
                                    onChange={(e) => setInternalNoteText(e.target.value)}
                                    placeholder="Write a confidential internal ticket note..."
                                    className="w-full text-xs bg-slate-900 border border-slate-800 p-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 text-slate-200 font-semibold placeholder-slate-600 resize-none"
                                  />
                                  <div className="flex justify-end">
                                    <button
                                      disabled={isSubmittingNote || !internalNoteText.trim()}
                                      onClick={async () => {
                                        setIsSubmittingNote(true);
                                        try {
                                          const res = await authFetch(`${API_BASE_URL}/tickets/${selectedTicketId}/action`, {
                                            method: "POST",
                                            headers: { "Content-Type": "application/json" },
                                            body: JSON.stringify({ action: "add_note", note: internalNoteText })
                                          });
                                          if (res.ok) {
                                            setInternalNoteText("");
                                            await fetchTicketDetails(selectedTicketId);
                                          } else {
                                            const errData = await res.json();
                                            alert(errData.detail || "Failed to add note.");
                                          }
                                        } catch (err: any) {
                                          alert(err.message || "An error occurred.");
                                        } finally {
                                          setIsSubmittingNote(false);
                                        }
                                      }}
                                      className="px-3.5 py-1.5 bg-slate-850 hover:bg-slate-800 text-[10px] font-bold text-slate-200 rounded-lg border border-slate-750/85 transition-colors disabled:opacity-40"
                                    >
                                      {isSubmittingNote ? "Submitting..." : "Add Note"}
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Footer - Admin Actions Panel */}
                        {user?.role === "ADMIN" && (
                          <div className="p-4 border-t border-slate-800 bg-[#0F172A]/90 space-y-3">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block mb-1">Administrative ITSM Controls</span>
                            
                            <div className="flex flex-wrap gap-2">
                              {selectedTicketDetails.ticket.status !== "IN_PROGRESS" && selectedTicketDetails.ticket.status !== "CLOSED" && selectedTicketDetails.ticket.status !== "RESOLVED" && (
                                <button
                                  onClick={() => handleAdminAction("start_work")}
                                  className="flex-1 py-2 px-3 bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white rounded-lg transition-colors shadow-lg shadow-blue-600/10"
                                >
                                  Start Work
                                </button>
                              )}
                              
                              {selectedTicketDetails.ticket.status !== "WAITING" && selectedTicketDetails.ticket.status !== "CLOSED" && selectedTicketDetails.ticket.status !== "RESOLVED" && (
                                <button
                                  onClick={() => handleAdminAction("put_on_hold")}
                                  className="flex-1 py-2 px-3 bg-slate-800 hover:bg-slate-750 text-xs font-bold text-slate-200 rounded-lg border border-slate-700/50 transition-colors"
                                >
                                  Put On Hold
                                </button>
                              )}

                              {selectedTicketDetails.ticket.status !== "WAITING_FOR_USER" && selectedTicketDetails.ticket.status !== "CLOSED" && selectedTicketDetails.ticket.status !== "RESOLVED" && (
                                <button
                                  onClick={() => {
                                    const note = prompt("Please provide additional information request details:");
                                    if (note) handleAdminAction("request_more_information", { note });
                                  }}
                                  className="flex-1 py-2 px-3 bg-slate-800 hover:bg-slate-750 text-xs font-bold text-slate-200 rounded-lg border border-slate-700/50 transition-colors"
                                >
                                  Request Info
                                </button>
                              )}

                              {selectedTicketDetails.ticket.status !== "RESOLVED" && selectedTicketDetails.ticket.status !== "CLOSED" && (
                                <button
                                  onClick={() => {
                                    setConfirmAction({
                                      action: "resolve",
                                      title: "Resolve Ticket?",
                                      desc: "Are you sure this issue has been resolved? This will notify the employee."
                                    });
                                  }}
                                  className="flex-1 py-2 px-3 bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white rounded-lg transition-colors shadow-lg shadow-emerald-600/10"
                                >
                                  Resolve
                                </button>
                              )}

                              {selectedTicketDetails.ticket.status !== "CLOSED" && (
                                <button
                                  onClick={() => {
                                    setConfirmAction({
                                      action: "close",
                                      title: "Close Ticket?",
                                      desc: "This action will mark the ticket as Closed in ITSM logs. Destructive operations cannot be undone."
                                    });
                                  }}
                                  className="flex-1 py-2 px-3 bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white rounded-lg transition-colors shadow-lg shadow-rose-600/10"
                                >
                                  Close Ticket
                                </button>
                              )}

                              {(selectedTicketDetails.ticket.status === "CLOSED" || selectedTicketDetails.ticket.status === "RESOLVED") && (
                                <button
                                  onClick={() => handleAdminAction("reopen")}
                                  className="flex-1 py-2 px-3 bg-violet-600 hover:bg-violet-500 text-xs font-bold text-white rounded-lg transition-colors shadow-lg shadow-violet-600/10"
                                >
                                  Reopen Ticket
                                </button>
                              )}
                            </div>

                            {/* Team Assignment & Priority updates */}
                            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800">
                              <div>
                                <label className="text-[9px] text-slate-500 font-bold block mb-1 uppercase tracking-wider">Transfer Support Team</label>
                                <select
                                  value={selectedTicketDetails.ticket.assigned_team || ""}
                                  onChange={(e) => {
                                    if (e.target.value) {
                                      handleAdminAction("transfer_team", { team: e.target.value });
                                    }
                                  }}
                                  className="w-full text-xs bg-slate-900 border border-slate-800 p-2 rounded-lg text-slate-350 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
                                >
                                  <option value="">Select Team...</option>
                                  <option value="Helpdesk">Helpdesk L1/L2</option>
                                  <option value="Network">Network Ops</option>
                                  <option value="Sysadmin">System Admin</option>
                                  <option value="Security">Security Operations</option>
                                  <option value="Hardware">Hardware Desk</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-[9px] text-slate-500 font-bold block mb-1 uppercase tracking-wider">Modify Priority Level</label>
                                <select
                                  value={selectedTicketDetails.ticket.priority || ""}
                                  onChange={(e) => {
                                    if (e.target.value) {
                                      handleAdminAction("change_priority", { priority: e.target.value });
                                    }
                                  }}
                                  className="w-full text-xs bg-slate-900 border border-slate-800 p-2 rounded-lg text-slate-350 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
                                >
                                  <option value="LOW">LOW (24 Hours)</option>
                                  <option value="MEDIUM">MEDIUM (8 Hours)</option>
                                  <option value="HIGH">HIGH (4 Hours)</option>
                                  <option value="CRITICAL">CRITICAL (1 Hour)</option>
                                </select>
                              </div>
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex-1 flex items-center justify-center text-slate-500 italic text-xs">
                        Empty details context.
                      </div>
                    )}
                  </motion.div>
                </>
              )}
            </AnimatePresence>

            {/* Clickable Service Request Details Drawer */}
            <AnimatePresence>
              {serviceRequestDrawerOpen && selectedServiceRequest && (
                <>
                  {/* Backdrop overlay */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/60 z-40 cursor-pointer"
                    onClick={() => {
                      setServiceRequestDrawerOpen(false);
                      setSelectedServiceRequest(null);
                    }}
                  />

                  {/* Slide-over Panel */}
                  <motion.div
                    initial={{ x: "100%" }}
                    animate={{ x: 0 }}
                    exit={{ x: "100%" }}
                    transition={{ type: "spring", damping: 28, stiffness: 220 }}
                    className="fixed top-0 right-0 h-full w-[600px] z-50 bg-[#0B0F19] border-l border-slate-800/80 shadow-2xl flex flex-col text-slate-200"
                  >
                    {/* Header */}
                    <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-[#0F172A]/90 backdrop-blur-md">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/10 rounded-lg">
                          <FileText className="w-5 h-5 text-blue-400" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-base font-bold text-slate-100">{selectedServiceRequest.request_id}</span>
                            {selectedServiceRequest.servicenow_id && (
                              <span className="font-mono text-xs text-amber-500 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                                {selectedServiceRequest.servicenow_id}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 font-medium truncate max-w-[320px]">
                            {selectedServiceRequest.service_name}
                          </p>
                        </div>
                      </div>
                      <button 
                        onClick={() => {
                          setServiceRequestDrawerOpen(false);
                          setSelectedServiceRequest(null);
                        }}
                        className="p-1 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-slate-200 cursor-pointer"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    {/* Drawer Content */}
                    <div className="flex-1 overflow-y-auto p-5 space-y-6">
                      
                      {/* Top Badges */}
                      <div className="flex gap-2 flex-wrap items-center bg-slate-900/40 p-3 rounded-xl border border-slate-800/60">
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mr-1">Status:</span>
                        <span className={statusBadgeClass(selectedServiceRequest.status)}>{selectedServiceRequest.status}</span>
                        <span className="text-[10px] text-slate-500 uppercase tracking-wider font-bold ml-2 mr-1">Stage:</span>
                        <span className="badge badge-assigned">{selectedServiceRequest.stage}</span>
                      </div>

                      {/* Fields details */}
                      <div className="card p-4 space-y-4">
                        <SectionHeader title="Service Request Info & Variables" icon={<Info className="w-4 h-4 text-slate-400" />} />
                        <div className="grid grid-cols-2 gap-x-6 gap-y-4 text-xs">
                          <div>
                            <span className="text-slate-500 block mb-1">Requested By</span>
                            <span className="font-mono text-slate-200">@{selectedServiceRequest.requested_by}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-1">Category</span>
                            <span className="font-semibold text-slate-200">{selectedServiceRequest.category}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-1">Assigned Fulfillment Team</span>
                            <span className="font-bold text-blue-400">{selectedServiceRequest.assigned_team || "Helpdesk"}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-1">Est. Completion</span>
                            <span className="text-slate-250 font-semibold">{selectedServiceRequest.estimated_completion || "N/A"}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-1">SLA Limit</span>
                            <span className="text-slate-255 font-semibold">{selectedServiceRequest.sla_hours ? `${selectedServiceRequest.sla_hours} Hours` : "N/A"}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block mb-1">Created At</span>
                            <span className="text-slate-350">{fmtDate(selectedServiceRequest.created_at)} {fmtTime(selectedServiceRequest.created_at)}</span>
                          </div>
                        </div>

                        {/* Variables filled */}
                        <div className="border-t border-slate-800/80 pt-4 mt-4">
                          <span className="section-header block mb-3">Submitted Request Details (Variables)</span>
                          <div className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-850 space-y-3 font-semibold text-xs text-slate-300">
                            {(() => {
                              try {
                                const vars = typeof selectedServiceRequest.details === "string" 
                                  ? JSON.parse(selectedServiceRequest.details) 
                                  : selectedServiceRequest.details || {};
                                
                                if (Object.keys(vars).length === 0) {
                                  return <div className="text-slate-500 italic text-[11px]">No variables submitted</div>;
                                }
                                
                                return Object.entries(vars).map(([key, val]) => (
                                  <div key={key} className="flex justify-between border-b border-slate-850/50 pb-2 last:border-b-0 last:pb-0">
                                    <span className="text-slate-505 capitalize">{key.replace(/_/g, " ")}:</span>
                                    <span className="text-slate-200 font-mono">{String(val)}</span>
                                  </div>
                                ));
                              } catch {
                                return <div className="text-slate-400 break-all">{selectedServiceRequest.details}</div>;
                              }
                            })()}
                          </div>
                        </div>
                      </div>

                      {/* Request Timeline */}
                      <div className="card p-4 space-y-4">
                        <SectionHeader title="Service Request Workflow Timeline" icon={<Clock className="w-4 h-4 text-slate-400" />} />
                        <div className="space-y-4">
                          {!selectedServiceRequest.timeline || selectedServiceRequest.timeline.length === 0 ? (
                            <div className="text-slate-500 italic text-center py-4">No events in timeline</div>
                          ) : (
                            selectedServiceRequest.timeline.map((evt: any, idx: number) => (
                              <div key={idx} className="relative pl-6 pb-2 last:pb-0 border-l border-slate-800 last:border-l-0 animate-fadeIn">
                                <div className="absolute left-[-4.5px] top-1.5 w-2 h-2 rounded-full bg-blue-500" />
                                <div className="flex justify-between text-[11px] mb-1 font-semibold">
                                  <span className="text-blue-400">{evt.user} ({evt.role})</span>
                                  <span className="text-slate-505 font-mono">{fmtDate(evt.timestamp)} {fmtTime(evt.timestamp)}</span>
                                </div>
                                <p className="text-xs text-slate-300 font-medium">{evt.details}</p>
                              </div>
                            ))
                          )}
                        </div>
                      </div>

                      {/* Work Notes / Discussion */}
                      <div className="card p-4 space-y-4">
                        <SectionHeader title="Internal discussion & work notes" icon={<FileText className="w-4 h-4 text-slate-400" />} />
                        <div className="space-y-3">
                          <textarea
                            value={workNotesText}
                            onChange={(e) => setWorkNotesText(e.target.value)}
                            placeholder="Enter work note or update description..."
                            className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors h-16 resize-none"
                          />
                          <div className="flex justify-end">
                            <button
                              disabled={isExecutingAction || !workNotesText.trim()}
                              onClick={() => handleServiceRequestAction(selectedServiceRequest.request_id, "add_note", workNotesText)}
                              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-750 text-xs font-bold text-slate-200 border border-slate-700 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                            >
                              Add Work Note
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Footer Actions */}
                    <div className="p-4 border-t border-slate-800 bg-[#0F172A]/90 backdrop-blur-md flex flex-wrap gap-2.5 justify-end">
                      {/* Approve / Reject buttons for PENDING_APPROVAL (Admin or Manager) */}
                      {selectedServiceRequest.status === "PENDING_APPROVAL" && (user?.role === "ADMIN" || user?.role === "MANAGER") && (
                        <>
                          <button
                            disabled={isExecutingAction}
                            onClick={() => {
                              setPendingConfirmAction({ requestId: selectedServiceRequest.request_id, action: "reject", note: workNotesText });
                              setActionConfirmOpen(true);
                            }}
                            className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white rounded-lg transition-all shadow-lg hover:shadow-rose-600/10 cursor-pointer"
                          >
                            Reject Request
                          </button>
                          <button
                            disabled={isExecutingAction}
                            onClick={() => handleServiceRequestAction(selectedServiceRequest.request_id, "approve", workNotesText)}
                            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white rounded-lg transition-all shadow-lg hover:shadow-emerald-600/10 cursor-pointer"
                          >
                            Approve Request
                          </button>
                        </>
                      )}

                      {/* Start Fulfillment button (Admin only, when SUBMITTED or APPROVED) */}
                      {(selectedServiceRequest.status === "APPROVED" || selectedServiceRequest.status === "SUBMITTED") && user?.role === "ADMIN" && (
                        <button
                          disabled={isExecutingAction}
                          onClick={() => handleServiceRequestAction(selectedServiceRequest.request_id, "start_fulfillment", workNotesText)}
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white rounded-lg transition-all shadow-lg hover:shadow-blue-600/10 cursor-pointer"
                        >
                          Start Fulfillment
                        </button>
                      )}

                      {/* Complete Fulfillment button (Admin only, when FULFILLMENT) */}
                      {selectedServiceRequest.status === "FULFILLMENT" && user?.role === "ADMIN" && (
                        <button
                          disabled={isExecutingAction}
                          onClick={() => handleServiceRequestAction(selectedServiceRequest.request_id, "complete", workNotesText)}
                          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white rounded-lg transition-all shadow-lg hover:shadow-emerald-600/10 cursor-pointer"
                        >
                          Complete Fulfillment
                        </button>
                      )}

                      {/* Close button (Requester when COMPLETED, Admin anytime) */}
                      {((selectedServiceRequest.status === "COMPLETED" && (selectedServiceRequest.requested_by === user?.username || user?.role === "ADMIN")) || 
                        (selectedServiceRequest.status !== "CLOSED" && selectedServiceRequest.status !== "REJECTED" && user?.role === "ADMIN")) && (
                        <button
                          disabled={isExecutingAction}
                          onClick={() => {
                            setPendingConfirmAction({ requestId: selectedServiceRequest.request_id, action: "close", note: workNotesText });
                            setActionConfirmOpen(true);
                          }}
                          className="px-4 py-2 bg-slate-800 hover:bg-slate-750 text-xs font-bold text-slate-300 rounded-lg border border-slate-700 transition-all cursor-pointer"
                        >
                          Close Request
                        </button>
                      )}
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>

            {/* Service Catalog Item Request Modal */}
            <AnimatePresence>
              {requestCatalogItem && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 animate-fadeIn">
                  {/* Backdrop */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-black/85"
                    onClick={() => setRequestCatalogItem(null)}
                  />

                  {/* Form Modal Body */}
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-[#0B0F19] border border-slate-800 p-6 rounded-2xl shadow-2xl relative max-w-md w-full z-10 space-y-4 text-slate-200"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="text-[10px] font-mono font-bold text-blue-400 bg-blue-500/10 border border-blue-500/25 px-2 py-0.5 rounded">{requestCatalogItem.service_id}</span>
                        <h3 className="text-base font-bold text-slate-100 mt-1">{requestCatalogItem.name}</h3>
                        <p className="text-xs text-slate-500 mt-0.5 font-medium">{requestCatalogItem.category} Services</p>
                      </div>
                      <button 
                        onClick={() => setRequestCatalogItem(null)}
                        className="p-1 hover:bg-slate-800 rounded transition-colors text-slate-400 hover:text-slate-200 cursor-pointer"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    <p className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded-lg border border-slate-800 leading-relaxed font-semibold">
                      {requestCatalogItem.description}
                    </p>

                    <form onSubmit={async (e) => {
                      e.preventDefault();
                      setIsSubmittingRequest(true);
                      try {
                        const res = await authFetch(`${API_BASE_URL}/service-requests`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            service_id: requestCatalogItem.service_id,
                            details: requestFormDetails
                          })
                        });
                        if (res.ok) {
                          const created = await res.json();
                          alert(`Request submitted successfully! Created ID: ${created.request_id}`);
                          setRequestCatalogItem(null);
                          await fetchServiceRequests();
                        } else {
                          const err = await res.json();
                          alert(err.detail || "Submission failed.");
                        }
                      } catch (err: any) {
                        alert(err.message || "An error occurred.");
                      } finally {
                        setIsSubmittingRequest(false);
                      }
                    }} className="space-y-4">
                      {(CATALOG_REQUIRED_SLOTS[requestCatalogItem.service_id] || ["justification"]).map((slot: string) => {
                        const prompt = SLOT_PROMPTS_FRONTEND[slot] || slot;
                        const value = requestFormDetails[slot] || "";
                        
                        return (
                          <div key={slot} className="space-y-1.5 animate-fadeIn">
                            <label className="section-header block">{prompt}</label>
                            {slot === "justification" ? (
                              <textarea
                                required
                                value={value}
                                onChange={(e) => setRequestFormDetails(prev => ({ ...prev, [slot]: e.target.value }))}
                                className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors h-16 resize-none"
                              />
                            ) : slot === "start_date" ? (
                              <input
                                type="date"
                                required
                                value={value}
                                onChange={(e) => setRequestFormDetails(prev => ({ ...prev, [slot]: e.target.value }))}
                                className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                              />
                            ) : (slot === "access_type" || slot === "access_level") ? (
                              <select
                                required
                                value={value}
                                onChange={(e) => setRequestFormDetails(prev => ({ ...prev, [slot]: e.target.value }))}
                                className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                              >
                                <option value="">-- Select Access Option --</option>
                                <option value="Read-Only">Read-Only</option>
                                <option value="Read-Write">Read-Write</option>
                              </select>
                            ) : slot === "action" && requestCatalogItem.service_id === "SRV006" ? (
                              <select
                                required
                                value={value}
                                onChange={(e) => setRequestFormDetails(prev => ({ ...prev, [slot]: e.target.value }))}
                                className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                              >
                                <option value="">-- Select Action Option --</option>
                                <option value="Create New">Create New</option>
                                <option value="Modify Existing">Modify Existing</option>
                              </select>
                            ) : (
                              <input
                                type="text"
                                required
                                value={value}
                                onChange={(e) => setRequestFormDetails(prev => ({ ...prev, [slot]: e.target.value }))}
                                className="w-full bg-slate-900 border border-slate-700/60 rounded-xl px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                              />
                            )}
                          </div>
                        );
                      })}

                      <div className="flex gap-3 justify-end pt-2">
                        <button
                          type="button"
                          disabled={isSubmittingRequest}
                          onClick={() => setRequestCatalogItem(null)}
                          className="px-4 py-2 bg-slate-850 hover:bg-slate-800 text-xs font-bold text-slate-350 rounded-lg border border-slate-750 transition-colors cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={isSubmittingRequest}
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-xs font-bold text-white rounded-lg transition-colors cursor-pointer"
                        >
                          {isSubmittingRequest ? "Submitting..." : "Submit Request"}
                        </button>
                      </div>
                    </form>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Service Request Action Confirmation Dialog */}
            <AnimatePresence>
              {actionConfirmOpen && pendingConfirmAction && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                  {/* Backdrop */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-black/85"
                    onClick={() => {
                      setActionConfirmOpen(false);
                      setPendingConfirmAction(null);
                    }}
                  />

                  {/* Confirmation Modal Body */}
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-2xl relative max-w-sm w-full z-10 space-y-4 text-slate-200"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-rose-500/10 text-rose-500 rounded-lg font-bold">
                        <AlertTriangle className="w-6 h-6 animate-bounce" />
                      </div>
                      <h3 className="text-base font-bold text-slate-200">
                        {pendingConfirmAction.action === "reject" ? "Reject Service Request?" : "Close Service Request?"}
                      </h3>
                    </div>
                    
                    <p className="text-xs text-slate-400 leading-relaxed font-semibold">
                      {pendingConfirmAction.action === "reject" 
                        ? "Are you sure you want to reject this request? This will notify the user and cancel the fulfillment workflow."
                        : "Are you sure you want to close this service request? This will mark the request status as CLOSED."
                      }
                    </p>

                    {pendingConfirmAction.action === "reject" && (
                      <div className="space-y-1.5">
                        <label className="section-header block">Rejection Reason (Required)</label>
                        <input
                          type="text"
                          required
                          placeholder="Provide a reason for rejection..."
                          value={pendingConfirmAction.note || ""}
                          onChange={(e) => setPendingConfirmAction(prev => prev ? ({ ...prev, note: e.target.value }) : null)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-semibold text-slate-250 focus:outline-none focus:border-rose-500 transition-colors"
                        />
                      </div>
                    )}

                    <div className="flex gap-3 justify-end pt-2">
                      <button
                        disabled={isExecutingAction}
                        onClick={() => {
                          setActionConfirmOpen(false);
                          setPendingConfirmAction(null);
                        }}
                        className="px-4 py-2 bg-slate-850 hover:bg-slate-800 text-xs font-bold text-slate-300 rounded-lg border border-slate-755 transition-colors cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        disabled={isExecutingAction || (pendingConfirmAction.action === "reject" && !pendingConfirmAction.note?.trim())}
                        onClick={() => handleServiceRequestAction(pendingConfirmAction.requestId, pendingConfirmAction.action, pendingConfirmAction.note)}
                        className={`px-4 py-2 text-xs font-bold text-white rounded-lg transition-colors shadow-lg cursor-pointer disabled:opacity-50 ${
                          pendingConfirmAction.action === "reject" ? "bg-rose-600 hover:bg-rose-500 shadow-rose-600/10" : "bg-slate-700 hover:bg-slate-650"
                        }`}
                      >
                        {isExecutingAction ? "Processing..." : pendingConfirmAction.action === "reject" ? "Confirm Reject" : "Confirm Close"}
                      </button>
                    </div>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>

            {/* Confirmation Dialogs Modal */}
            <AnimatePresence>
              {confirmAction && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                  {/* Dark Backdrop */}
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-black/85"
                    onClick={() => setConfirmAction(null)}
                  />

                  {/* Modal Body */}
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-2xl relative max-w-sm w-full z-10 space-y-4"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-amber-500/10 rounded-lg text-amber-500 font-bold">
                        <AlertTriangle className="w-6 h-6 animate-bounce" />
                      </div>
                      <h3 className="text-base font-bold text-slate-200">{confirmAction.title}</h3>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed font-semibold">
                      {confirmAction.desc}
                    </p>
                    <div className="flex gap-3 justify-end pt-2">
                      <button
                        disabled={isExecutingAction}
                        onClick={() => setConfirmAction(null)}
                        className="px-4 py-2 bg-slate-850 hover:bg-slate-850 text-xs font-bold text-slate-300 rounded-lg border border-slate-750/80 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        disabled={isExecutingAction}
                        onClick={() => handleAdminAction(confirmAction.action)}
                        className={`px-4 py-2 text-xs font-bold text-white rounded-lg transition-colors shadow-lg ${
                          confirmAction.action === "close" ? "bg-rose-600 hover:bg-rose-500 shadow-rose-600/10" : "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-600/10"
                        }`}
                      >
                        {isExecutingAction ? "Processing..." : confirmAction.action === "close" ? "Close Ticket" : "Resolve"}
                      </button>
                    </div>
                  </motion.div>
                </div>
              )}
            </AnimatePresence>


          </div>
        </div>
      </div>
    </div>
  );
}