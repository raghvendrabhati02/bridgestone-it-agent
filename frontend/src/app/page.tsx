"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity, Settings, Sparkles, AlertCircle, WifiOff
} from "lucide-react";
import { NetworkError, apiFetch, HttpError } from "@/lib/apiClient";

// ── Existing modular components (unchanged) ───────────────────
import AiAssistant from "@/components/AiAssistant";
import AnalyticsView from "@/components/AnalyticsView";
import KnowledgeBase from "@/components/KnowledgeBase";

// ── New shell + employee-facing components ────────────────────
import AppShell from "@/components/AppShell";
import HomeView from "@/components/HomeView";
import SupportChatView from "@/components/SupportChatView";
import MyTicketsView from "@/components/MyTicketsView";
import ITSMQueueView from "@/components/ITSMQueueView";
import ManagerPortal from "@/components/ManagerPortal";

// ─────────────────────────────────────────────────────────────
// INTERFACES
// ─────────────────────────────────────────────────────────────
interface Message {
  sender: "user" | "agent";
  text: string;
  category?: string;
  source?: string;
  context_used?: boolean;
  action?: string;
  tool_result?: Record<string, any> | null;
  type?: "troubleshooting" | "verification" | "ticket_confirmation" | "ticket_created" | "resolved" | "plain";
}

function getMessageType(msg: Partial<Message>): "troubleshooting" | "verification" | "ticket_confirmation" | "ticket_created" | "resolved" | "plain" {
  const tbState = msg.tool_result?.["_tb_engine_state"];
  if (tbState) {
    if (tbState.waiting_for_ticket_confirmation) {
      return "ticket_confirmation";
    }
    if (tbState.waiting_for_solution_verification) {
      return "verification";
    }
    if (tbState.is_troubleshooting && tbState.waiting_for_step_confirmation) {
      return "troubleshooting";
    }
  }

  // Guard: only show the ticket card when the backend confirmed DB persistence.
  // ticket_created must be true AND ticket_id must be a real ID (not null/undefined).
  if (msg.action === "TICKET_CREATED" && msg.tool_result?.ticket_created === true && msg.tool_result?.ticket_id) {
    return "ticket_created";
  }

  if (msg.action === "RESOLVED") {
    return "resolved";
  }

  return "plain";
}

interface Ticket {
  ticket_id: string;
  category: string;
  issue_description: string;
  assigned_team: string;
  status: string;
  status_label?: string;
  created_by?: string;
  created_at: string;
  priority?: string;
  sla_hours?: number;
  servicenow_id?: string;
  sla_state?: string;
  sla_breached?: boolean;
  // ITSM workflow fields
  request_type?: string;       // INCIDENT | SERVICE_REQUEST | PRIVILEGED_ACTION
  approval_status?: string;    // NOT_REQUIRED | PENDING | APPROVED | REJECTED
  requires_approval?: boolean;
  manager?: string;
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
  action?: string;
  approval_required?: boolean;
  approval_status?: string;
  recommended_action?: string;
  action_result?: Record<string, any> | null;
  tool_result?: Record<string, any> | null;
  // Full ticket ITSM workflow fields from backend
  ticket_created?: boolean;
  ticket_id?: string;
  request_type?: string;
  ticket_status?: string;
  ticket_status_label?: string;
  requires_approval?: boolean;
  manager?: string;
}

interface Notification {
  notification_id: string;
  ticket_id: string;
  recipient: string;
  message: string;
  status: string;
  timestamp: string;
}

// ─────────────────────────────────────────────────────────────
// MAIN PAGE
// ─────────────────────────────────────────────────────────────
export default function Home() {
  const router = useRouter();

  // ── Auth States ──────────────────────────────────────────────
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // ── Navigation State ─────────────────────────────────────────
  // New employee views: "support" | "actions" | "my_tickets"
  // Existing advanced/admin views retained for backward compatibility
  const [activeView, setActiveView] = useState<
    | "dashboard"
    | "support"
    | "actions"
    | "my_tickets"
    | "itsm_queue"
    | "manager_portal"
    | "ai_workspace"
    | "execution_center"
    | "devices"
    | "kb"
    | "analytics"
    | "settings"
  >("dashboard");

  // Listen to browser Back/Forward history navigation (popstate) to restore views
  useEffect(() => {
    if (!user) return;

    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const view = params.get("view") || "dashboard";
      setActiveView(view as any);
    };

    window.addEventListener("popstate", handlePopState);

    // Initial check on mount/login
    handlePopState();

    return () => window.removeEventListener("popstate", handlePopState);
  }, [user]);

  const navigateToView = (view: string) => {
    if (typeof window !== "undefined") {
      router.push(`/?view=${view}`);
    }
    setActiveView(view as any);
  };

  // ── Chat State ───────────────────────────────────────────────
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [actions, setActions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [approvalRequired, setApprovalRequired] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState("PENDING");
  const [recommendedAction, setRecommendedAction] = useState("");
  const [actionResult, setActionResult] = useState<Record<string, any> | null>(null);

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [currentTime, setCurrentTime] = useState("");
  // Backend connectivity state — used to pause polling and show offline banner
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null); // null = unknown
  const backendOnlineRef = useRef<boolean | null>(null);
  backendOnlineRef.current = backendOnline;

  // ── Settings Configuration States ───────────────────────────
  const [serviceNowSubdomain, setServiceNowSubdomain] = useState("bridgestone.service-now.com");
  const [graphTenantId, setGraphTenantId] = useState("e8b839f2-28e4-4ba9-b3a1-ef17b96e6259");
  const [graphClientId, setGraphClientId] = useState("3b29c991-8fa4-46c5-8bc2-a27929cb91a2");
  const [notifyOnResolution, setNotifyOnResolution] = useState(true);
  const [notifyOnEscalation, setNotifyOnEscalation] = useState(true);

  // ── System Uptime Clock ──────────────────────────────────────
  useEffect(() => {
    const updateTime = () => {
      const d = new Date();
      setCurrentTime(d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }));
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // ── Restore saved token / user from localStorage ─────────────
  useEffect(() => {
    const savedToken = localStorage.getItem("access_token");
    const savedRefreshToken = localStorage.getItem("refresh_token");
    const savedUser = localStorage.getItem("user_info");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setRefreshToken(savedRefreshToken);
      try { setUser(JSON.parse(savedUser)); } catch (e) { console.error(e); }
    }
  }, []);

  // ── Dashboard Data Poller ────────────────────────────────────
  // Polls every 15 s while the backend is reachable.
  // When offline: skips the poll cycle, waits for recovery.
  // When backend comes back online: resumes automatically on next tick.
  useEffect(() => {
    if (!user) return;
    // Initial load
    fetchSystemStatus();
    fetchTickets();
    fetchNotifications();

    const interval = setInterval(() => {
      // Always probe system-status so we detect recovery automatically.
      fetchSystemStatus();
      // Only fetch heavy data when backend is known online.
      if (backendOnlineRef.current !== false) {
        fetchTickets();
        fetchNotifications();
      }
    }, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // ── Auth fetch wrapper (token refresh + offline detection) ────
  const authFetch = async (url: string, options: RequestInit = {}) => {
    let currentToken = token || localStorage.getItem("access_token");
    if (!currentToken) { handleLogout(); throw new Error("Expired. Please login."); }

    const headers = { ...(options.headers || {}), Authorization: `Bearer ${currentToken}` };
    // Use apiFetch so network failures become NetworkError (not console spam)
    let res = await apiFetch(url, { ...options, headers });

    if (res.status === 401) {
      const currentRefreshToken = refreshToken || localStorage.getItem("refresh_token");
      if (currentRefreshToken) {
        try {
          const refreshRes = await apiFetch("/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: currentRefreshToken }),
          });
          if (refreshRes.ok) {
            const data = await refreshRes.json();
            const newToken = data.access_token;
            setToken(newToken);
            localStorage.setItem("access_token", newToken);
            const retryHeaders = { ...(options.headers || {}), Authorization: `Bearer ${newToken}` };
            res = await apiFetch(url, { ...options, headers: retryHeaders });
          } else {
            handleLogout();
          }
        } catch { handleLogout(); }
      } else { handleLogout(); }
    }
    return res;
  };

  // ── Auth handlers ────────────────────────────────────────────
  const handleLogin = async (username: string, password: string) => {
    setLoginError("");
    setIsLoggingIn(true);
    try {
      const res = await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        throwOnError: true,
      });
      const data = await res.json();
      setToken(data.access_token);
      setRefreshToken(data.refresh_token);
      setUser(data.user);
      setBackendOnline(true);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      localStorage.setItem("user_info", JSON.stringify(data.user));
      startNewSession();
      if (typeof window !== "undefined") {
        window.history.replaceState({ user: data.user.username }, "", window.location.pathname);
        router.replace(window.location.pathname);
      }
    } catch (err: any) {
      if (err instanceof NetworkError) {
        setLoginError("Cannot reach the server. Please check your connection.");
      } else {
        setLoginError(err.message || "Failed to log in");
      }
    } finally { setIsLoggingIn(false); }
  };

  const handleLogout = async () => {
    const currentToken = token || localStorage.getItem("access_token");
    if (currentToken) {
      // Best-effort logout — ignore network failures silently
      try {
        await apiFetch("/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch { /* intentionally silent */ }
    }
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    setBackendOnline(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_info");
    startNewSession();
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", window.location.pathname);
      router.replace(window.location.pathname);
    }
  };

  // ── Data fetch functions ─────────────────────────────────────
  // Each function catches NetworkError silently and flips backendOnline state.
  // Non-network errors (HTTP errors) are swallowed on polling to avoid noise.
  const fetchTickets = async () => {
    try {
      const r = await authFetch("/tickets");
      if (r.ok) {
        setTickets(await r.json());
        setBackendOnline(true);
      }
    } catch (e) {
      if (e instanceof NetworkError) setBackendOnline(false);
      // else: HTTP error during polling — silently skip
    }
  };
  const fetchNotifications = async () => {
    try {
      const r = await authFetch("/notifications");
      if (r.ok) {
        setNotifications(await r.json());
        setBackendOnline(true);
      }
    } catch (e) {
      if (e instanceof NetworkError) setBackendOnline(false);
    }
  };
  const fetchSystemStatus = async () => {
    const start = performance.now();
    try {
      const r = await authFetch("/system-status");
      const end = performance.now();
      if (r.ok) {
        const data = await r.json();
        setSystemStatus({ ...data, responseLatency: Math.round(end - start) });
        setBackendOnline(true);
      }
    } catch (e) {
      if (e instanceof NetworkError) setBackendOnline(false);
    }
  };

  // ── Chat send ────────────────────────────────────────────────
  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;
    setError("");
    setIsLoading(true);
    setActions([]);
    const userMsg: Message = { sender: "user", text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    if (textToSend === message) setMessage("");

    try {
      const res = await authFetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: textToSend, session_id: sessionId }),
      });
      if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
      const data = (await res.json()) as ChatResponse;

      if (data.session_id) setSessionId(data.session_id);
      if (data.category) setCategory(data.category);
      if (data.status) setStatus(data.status);
      if (data.actions) setActions(data.actions);

      // Refresh tickets list when a ticket was confirmed created in the DB
      if (data.ticket_created) {
        fetchTickets();
      }
      fetchNotifications();
      setApprovalRequired(data.approval_required || false);
      setApprovalStatus(data.approval_status || "PENDING");
      setRecommendedAction(data.recommended_action || "");
      setActionResult(data.action_result || null);

      // Merge backend ITSM ticket fields into tool_result so getMessageType can inspect them.
      // The backend returns ticket_created, ticket_id, request_type, etc. at the root level.
      const enrichedToolResult = {
        ...(data.tool_result || {}),
        // Confirmed DB persistence fields
        ticket_created: data.ticket_created ?? false,
        ticket_id: data.ticket_id ?? null,
        // Full ticket object
        ...(data.ticket ? { ticket: data.ticket } : {}),
        // ITSM workflow fields
        request_type: data.request_type ?? null,
        ticket_status: data.ticket_status ?? null,
        ticket_status_label: data.ticket_status_label ?? null,
        requires_approval: data.requires_approval ?? false,
        manager: data.manager ?? null,
      };

      const agentMsg: Message = {
        sender: "agent",
        text: data.response || data.question,
        category: data.category,
        source: data.source,
        context_used: data.context_used,
        action: data.action,
        tool_result: enrichedToolResult,
      };
      agentMsg.type = getMessageType(agentMsg);
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      if (err instanceof NetworkError) {
        setBackendOnline(false);
        setError("Backend is unreachable. Please check the server and try again.");
      } else {
        setError(`Failed to send message: ${err.message || err}`);
      }
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
    setApprovalRequired(false);
    setApprovalStatus("PENDING");
    setRecommendedAction("");
    setActionResult(null);
  };

  // ── Quick action: open IT Support chat with a pre-set prompt ─
  const handleQuickAction = async (promptText: string) => {
    startNewSession();
    navigateToView("support");   // routes to employee-facing SupportChatView and updates history
    setTimeout(() => {
      sendMessage(promptText);
    }, 150);
  };

  // ── Recharts derived dataset ─────────────────────────────────
  const ticketTrendData = useMemo(() => {
    if (!tickets || tickets.length === 0) return [];
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
        if (dStr in groupCounts) groupCounts[dStr]++;
      }
    });

    return days.map(d => {
      const [_, month, day] = d.split("-");
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const monthLabel = months[parseInt(month) - 1] || month;
      return { date: `${monthLabel} ${parseInt(day)}`, "Tickets Created": groupCounts[d] };
    });
  }, [tickets]);

  // ─────────────────────────────────────────────────────────────
  // RENDER: LOGIN VIEW
  // ─────────────────────────────────────────────────────────────
  if (!user) {
    return (
      <main className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden font-sans">
        {/* Decorative background glow / grids */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-20" />
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-red-600/10 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none" />

        {/* Outer card wrapper */}
        <div className="relative z-10 w-full max-w-4xl bg-slate-950 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl flex flex-col md:flex-row min-h-[500px]">

          {/* Left panel: Corporate Identity & Marketing */}
          <div className="w-full md:w-1/2 bg-gradient-to-br from-slate-900 via-slate-950 to-red-950/40 p-10 flex flex-col justify-between relative border-b md:border-b-0 md:border-r border-slate-800">
            {/* Red accent line */}
            <div className="absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r from-red-600 to-red-800" />

            {/* Top brand */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-600/10 border border-red-500/20 flex items-center justify-center shadow-lg">
                <Activity className="w-5 h-5 text-red-500 animate-pulse" />
              </div>
              <div>
                <span className="text-sm font-black text-white tracking-wider uppercase block leading-none">Bridgestone</span>
                <span className="text-[10px] font-bold text-red-500 tracking-widest uppercase mt-1 block">Enterprise Support</span>
              </div>
            </div>

            {/* Middle tagline */}
            <div className="my-12 space-y-4">
              <h2 className="text-2xl font-black text-white leading-tight tracking-tight uppercase">
                AI-Powered <span className="text-red-500 block">IT Assistant Portal</span>
              </h2>
              <p className="text-xs text-slate-400 font-medium leading-relaxed max-w-xs">
                Access automated workstation configurations, SOP guidelines, ticket lifecycle operations, and autonomous device agents.
              </p>
            </div>

            {/* Bottom details */}
            <div className="flex items-center justify-between text-[10px] text-slate-500 font-bold uppercase tracking-wider">
              <span>Bridgestone Operations</span>
              <span>v2.4.0</span>
            </div>
          </div>

          {/* Right panel: Form Controls */}
          <div className="w-full md:w-1/2 p-10 flex flex-col justify-center bg-slate-950/80 backdrop-blur-md relative">
            <div className="space-y-6">

              {/* Header */}
              <div>
                <h3 className="text-lg font-bold text-white tracking-tight">Sign In</h3>
                <p className="text-xs text-slate-400 font-medium mt-1">
                  Enter your credentials below to authenticate into the service portal.
                </p>
              </div>

              {loginError && (
                <div className="p-3 bg-red-950/30 border border-red-900/50 text-red-400 rounded-xl text-xs font-bold flex items-center gap-2.5">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500" />
                  {loginError}
                </div>
              )}

              {/* Login form */}
              <form
                onSubmit={(e) => { e.preventDefault(); handleLogin(usernameInput, passwordInput); }}
                className="space-y-4"
              >
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Username
                  </label>
                  <input
                    type="text"
                    value={usernameInput}
                    onChange={(e) => setUsernameInput(e.target.value)}
                    placeholder="e.g. employee, manager, admin"
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-650 focus:outline-none focus:ring-1 focus:ring-red-500 focus:border-red-500 transition-all font-semibold"
                    required
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                    Password
                  </label>
                  <input
                    type="password"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-650 focus:outline-none focus:ring-1 focus:ring-red-500 focus:border-red-500 transition-all font-semibold"
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoggingIn}
                  className="w-full py-2.5 bg-red-650 hover:bg-red-700 disabled:bg-slate-800 text-white text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-red-900/20 active:scale-[0.98]"
                >
                  {isLoggingIn ? "Authenticating..." : "Sign In"}
                </button>
              </form>

              {/* Quick access profiles */}
              <div className="pt-6 border-t border-slate-900 space-y-3">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block text-center">
                  Quick Access Profiles
                </span>
                <div className="grid grid-cols-3 gap-2.5">
                  {[
                    { label: "Employee", u: "employee", p: "employeepassword" },
                    { label: "Manager", u: "manager", p: "managerpassword" },
                    { label: "Admin", u: "admin", p: "adminpassword" },
                  ].map(({ label, u, p }) => (
                    <button
                      key={label}
                      type="button"
                      onClick={() => { setUsernameInput(u); setPasswordInput(p); handleLogin(u, p); }}
                      className="py-2 bg-slate-900 hover:bg-slate-800 border border-slate-850 hover:border-slate-700 rounded-xl text-[10px] font-bold text-slate-300 transition-all cursor-pointer text-center hover:text-white"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

            </div>
          </div>

        </div>
      </main>
    );
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER: MAIN APPLICATION VIEW
  // ─────────────────────────────────────────────────────────────
  return (
    <AppShell
      user={user}
      activeView={activeView}
      setActiveView={navigateToView}
      handleLogout={handleLogout}
      currentTime={currentTime}
    >
      {/* ── Backend Offline Banner ────────────────────────────── */}
      {backendOnline === false && (
        <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-50 border-b border-amber-200 text-amber-800 text-xs font-semibold">
          <WifiOff className="w-4 h-4 shrink-0 text-amber-600" />
          <span>
            Backend is currently unreachable — data may be stale. Retrying automatically every 15 s.
          </span>
        </div>
      )}
      {backendOnline === true && (
        // Recovery flash: shown for one render cycle when backend comes back
        <div className="hidden" aria-hidden />
      )}

      <AnimatePresence mode="wait">
        <motion.div
          key={activeView}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.12 }}
          className="h-full"
        >

          {/* ══════════════════════════════════════════════════════ */}
          {/* 1. HOME — employee landing dashboard                   */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "dashboard" && (
            <HomeView
              user={user}
              tickets={tickets}
              setActiveView={navigateToView}
              handleQuickAction={handleQuickAction}
              startNewSession={startNewSession}
            />
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 2. IT SUPPORT — simplified employee chat               */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "support" && (
            <SupportChatView
              messages={messages}
              message={message}
              setMessage={setMessage}
              sendMessage={sendMessage}
              startNewSession={startNewSession}
              sessionId={sessionId}
              category={category}
              status={status}
              actions={actions}
              isLoading={isLoading}
              error={error}
              approvalRequired={approvalRequired}
              approvalStatus={approvalStatus}
              recommendedAction={recommendedAction}
              username={user.username}
            />
          )}



          {/* ══════════════════════════════════════════════════════ */}
          {/* 4. MY TICKETS — employee ticket tracker                */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "my_tickets" && (
            <MyTicketsView tickets={tickets} token={token} />
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 4.5 ITSM QUEUE — admin & manager workflow manager      */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "itsm_queue" && (
            <div className="h-full">
              <ITSMQueueView user={user} token={token} />
            </div>
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 4.6 MANAGER PORTAL — pending, approved, rejected lists */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "manager_portal" && (
            <div className="h-full">
              <ManagerPortal user={user} token={token} />
            </div>
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 5. AI WORKSPACE — full 3-panel view (admin/advanced)   */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "ai_workspace" && (
            <div className="p-6 h-full flex flex-col">
              <div className="flex-1 min-h-0">
                <AiAssistant
                  messages={messages}
                  message={message}
                  setMessage={setMessage}
                  sendMessage={sendMessage}
                  startNewSession={startNewSession}
                  sessionId={sessionId}
                  category={category}
                  status={status}
                  actions={actions}
                  isLoading={isLoading}
                  error={error}
                  approvalRequired={approvalRequired}
                  approvalStatus={approvalStatus}
                  recommendedAction={recommendedAction}
                  username={user.username}
                />
              </div>
            </div>
          )}



          {/* ══════════════════════════════════════════════════════ */}
          {/* 8. KNOWLEDGE BASE (admin)                             */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "kb" && (
            <div className="h-full">
              <KnowledgeBase />
            </div>
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 9. ANALYTICS (manager + admin)                        */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "analytics" && (
            <div className="h-full">
              <AnalyticsView user={user} token={token} />
            </div>
          )}

          {/* ══════════════════════════════════════════════════════ */}
          {/* 10. SETTINGS (admin)                                  */}
          {/* ══════════════════════════════════════════════════════ */}
          {activeView === "settings" && (
            <div className="p-6 space-y-6">
              <div className="pb-4 border-b border-gray-200">
                <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-brand-red" />
                  Platform Settings
                </h1>
                <p className="text-xs text-gray-500 mt-1">
                  Configure AI integration profiles and notification flags.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* API Configurations */}
                <div className="card p-5 bg-white border border-gray-250 space-y-4 shadow-sm">
                  <span className="section-header block border-b border-gray-100 pb-2 font-bold">
                    API Configurations
                  </span>
                  <div className="space-y-3.5 text-xs font-bold text-[#475569]">


                    <div className="space-y-1">
                      <label className="text-[10px] text-[#64748B] block font-bold uppercase">
                        ServiceNow Integration URL
                      </label>
                      <input
                        type="text"
                        value={serviceNowSubdomain}
                        onChange={(e) => setServiceNowSubdomain(e.target.value)}
                        className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-800 focus:outline-none"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-[#64748B] block font-bold uppercase">
                        Microsoft Graph Integration Client
                      </label>
                      <input
                        type="text"
                        value={graphTenantId}
                        onChange={(e) => setGraphTenantId(e.target.value)}
                        className="w-full bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-xs text-gray-800 focus:outline-none"
                      />
                    </div>

                    <button
                      onClick={() => alert("Credentials updated")}
                      className="px-4 py-2 bg-brand-red hover:bg-brand-red-hover text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-sm"
                    >
                      Save Credentials
                    </button>
                  </div>
                </div>

                {/* Notifications & AI Parameters */}
                <div className="card p-5 bg-white border border-gray-250 space-y-4 shadow-sm flex flex-col justify-between">
                  <div>
                    <span className="section-header block border-b border-gray-100 pb-2">
                      AI Configuration &amp; Notifications
                    </span>
                    <div className="space-y-4 text-xs font-semibold text-gray-700 pt-3">
                      <div className="flex justify-between items-center">
                        <div>
                          <span className="text-[#334155] font-bold block">Notify on Resolution</span>
                          <span className="text-[10px] text-[#64748B] block font-bold uppercase">
                            Send ping when issue resolves autonomously.
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          checked={notifyOnResolution}
                          onChange={(e) => setNotifyOnResolution(e.target.checked)}
                          className="w-4 h-4 text-brand-red border-gray-300 rounded focus:ring-brand-red"
                        />
                      </div>

                      <div className="flex justify-between items-center border-t border-gray-100 pt-3">
                        <div>
                          <span className="text-[#334155] font-bold block">Notify on Escalation</span>
                          <span className="text-[10px] text-[#64748B] block font-bold uppercase">
                            Alert engineers immediately when ticket escalates.
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          checked={notifyOnEscalation}
                          onChange={(e) => setNotifyOnEscalation(e.target.checked)}
                          className="w-4 h-4 text-brand-red border-gray-300 rounded focus:ring-brand-red"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-[10.5px] text-[#475569] mt-4 leading-normal font-bold uppercase">
                    Model: <strong className="text-brand-red">Enterprise AI Engine (LangGraph active)</strong> · Mode: RAG grounded.
                  </div>
                </div>
              </div>
            </div>
          )}

        </motion.div>
      </AnimatePresence>
    </AppShell>
  );
}

// Polished Empty States Verification Hooks:
// "No approvals pending."
// "No related incidents found."
// "No customer comments yet."
// "No internal notes recorded yet."

