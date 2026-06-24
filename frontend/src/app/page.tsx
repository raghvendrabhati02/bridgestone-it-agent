"use client";

import { useState, useRef, useEffect } from "react";

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

export default function Home() {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  // Auth state
  const [user, setUser] = useState<any>(null);
  const [token, setToken] = useState<string | null>(null);

  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Chat interface state
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [category, setCategory] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [actions, setActions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Tab Selection
  const [activeRightTab, setActiveRightTab] = useState<"service_desk" | "admin_dashboard" | "monitoring">("service_desk");
  const [systemStatus, setSystemStatus] = useState<any>(null);

  // ServiceNow states
  const [servicenowIncidents, setServicenowIncidents] = useState<any[]>([]);
  const [servicenowRequests, setServicenowRequests] = useState<any[]>([]);

  // Microsoft Graph states
  const [graphUsers, setGraphUsers] = useState<any[]>([]);
  const [graphGroups, setGraphGroups] = useState<any[]>([]);

  // Azure AD / Entra ID states
  const [entraUsers, setEntraUsers] = useState<any[]>([]);
  const [entraGroups, setEntraGroups] = useState<any[]>([]);
  const [entraStats, setEntraStats] = useState<any>(null);

  // Approval states
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState("PENDING");
  const [recommendedAction, setRecommendedAction] = useState("");
  const [actionResult, setActionResult] = useState<Record<string, any> | null>(null);
  const [actionsHistory, setActionsHistory] = useState<any[]>([]);

  // Enterprise Log / Trace states
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [agentTraces, setAgentTraces] = useState<any[]>([]);
  const [securityLogs, setSecurityLogs] = useState<any[]>([]);

  // Ticketing states
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  
  // Notification states
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Hydrate auth state on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("access_token");
    const savedRefreshToken = localStorage.getItem("refresh_token");
    const savedUser = localStorage.getItem("user_info");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setRefreshToken(savedRefreshToken);
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {
        console.error("Failed to parse user info:", e);
      }
    }
  }, []);

  // Fetch dashboards whenever user state is set/changed
  useEffect(() => {
    let interval: any;
    if (user) {
      fetchTickets();
      fetchNotifications();
      if (user.role === "ADMIN" || user.role === "MANAGER") {
        fetchActionsHistory();
        fetchApprovals();
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
        interval = setInterval(() => {
          fetchSystemStatus();
          fetchServicenowIncidents();
          fetchServicenowRequests();
          fetchGraphUsers();
          fetchGraphGroups();
          fetchEntraUsers();
          fetchEntraGroups();
          fetchEntraStats();
        }, 15000);
      }
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [user]);

  // Auto-scroll to bottom of chat when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Authenticated fetch wrapper to attach JWT and handle token refresh
  const authFetch = async (url: string, options: RequestInit = {}) => {
    let currentToken = token || localStorage.getItem("access_token");
    if (!currentToken) {
      handleLogout();
      throw new Error("Session expired. Please log in again.");
    }

    const headers = {
      ...(options.headers || {}),
      "Authorization": `Bearer ${currentToken}`
    };

    let res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      console.log("Token expired, attempting automatic refresh...");
      const currentRefreshToken = refreshToken || localStorage.getItem("refresh_token");
      if (currentRefreshToken) {
        try {
          const refreshRes = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({ refresh_token: currentRefreshToken })
          });

          if (refreshRes.ok) {
            const data = await refreshRes.json();
            const newToken = data.access_token;
            setToken(newToken);
            localStorage.setItem("access_token", newToken);

            const retryHeaders = {
              ...(options.headers || {}),
              "Authorization": `Bearer ${newToken}`
            };
            res = await fetch(url, { ...options, headers: retryHeaders });
          } else {
            console.warn("Refresh token invalid or expired. Logging out.");
            handleLogout();
          }
        } catch (err) {
          console.error("Token refresh failed:", err);
          handleLogout();
        }
      } else {
        handleLogout();
      }
    }

    return res;
  };

  const handleLogin = async (username: string, password: string) => {
    setLoginError("");
    setIsLoggingIn(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Authentication failed");
      }

      const data = await res.json();
      setToken(data.access_token);
      setRefreshToken(data.refresh_token);
      setUser(data.user);
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      localStorage.setItem("user_info", JSON.stringify(data.user));

      // Reset application states
      startNewSession();
    } catch (err: any) {
      setLoginError(err.message || "Failed to log in");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = async () => {
    const currentToken = token || localStorage.getItem("access_token");
    if (currentToken) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${currentToken}`
          }
        });
      } catch (err) {
        console.error("Failed to call logout API:", err);
      }
    }
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user_info");
    startNewSession();
  };

  // Fetch ticket history
  const fetchTickets = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/tickets`);
      if (res.ok) {
        const data = await res.json() as Ticket[];
        setTickets(data);
      }
    } catch (err) {
      console.error("Failed to fetch tickets:", err);
    }
  };

  // Fetch notification logs
  const fetchNotifications = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/notifications`);
      if (res.ok) {
        const data = await res.json() as Notification[];
        setNotifications(data);
      }
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    }
  };

  // Fetch action logs
  const fetchActionsHistory = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/actions`);
      if (res.ok) {
        const data = await res.json();
        setActionsHistory(data);
      }
    } catch (err) {
      console.error("Failed to fetch actions history:", err);
    }
  };

  // Fetch audit logs
  const fetchAuditLogs = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/audit-logs`);
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch audit logs:", err);
    }
  };

  // Fetch approvals
  const fetchApprovals = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/approvals`);
      if (res.ok) {
        const data = await res.json();
        setApprovals(data);
      }
    } catch (err) {
      console.error("Failed to fetch approvals:", err);
    }
  };

  // Fetch agent traces
  const fetchAgentTraces = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/agent-traces`);
      if (res.ok) {
        const data = await res.json();
        setAgentTraces(data);
      }
    } catch (err) {
      console.error("Failed to fetch agent traces:", err);
    }
  };

  // Fetch security events logs (Admin only)
  const fetchSecurityLogs = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/admin/security-logs`);
      if (res.ok) {
        const data = await res.json();
        setSecurityLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch security logs:", err);
    }
  };

  // Fetch real-time system dependencies status (Admin only)
  const fetchSystemStatus = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/system-status`);
      if (res.ok) {
        const data = await res.json();
        setSystemStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    }
  };

  const fetchServicenowIncidents = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/servicenow/incidents`);
      if (res.ok) {
        const data = await res.json();
        setServicenowIncidents(data);
      }
    } catch (err) {
      console.error("Failed to fetch ServiceNow incidents:", err);
    }
  };

  const fetchServicenowRequests = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/servicenow/requests`);
      if (res.ok) {
        const data = await res.json();
        setServicenowRequests(data);
      }
    } catch (err) {
      console.error("Failed to fetch ServiceNow requests:", err);
    }
  };

  const fetchGraphUsers = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/microsoftgraph/users`);
      if (res.ok) {
        const data = await res.json();
        setGraphUsers(data);
      }
    } catch (err) {
      console.error("Failed to fetch Microsoft Graph users:", err);
    }
  };

  const fetchGraphGroups = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/microsoftgraph/groups`);
      if (res.ok) {
        const data = await res.json();
        setGraphGroups(data);
      }
    } catch (err) {
      console.error("Failed to fetch Microsoft Graph groups:", err);
    }
  };

  const fetchEntraUsers = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/entra/users`);
      if (res.ok) {
        const data = await res.json();
        setEntraUsers(data);
      }
    } catch (err) {
      console.error("Failed to fetch Entra users:", err);
    }
  };

  const fetchEntraGroups = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/entra/groups`);
      if (res.ok) {
        const data = await res.json();
        setEntraGroups(data);
      }
    } catch (err) {
      console.error("Failed to fetch Entra groups:", err);
    }
  };

  const fetchEntraStats = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/entra/stats`);
      if (res.ok) {
        const data = await res.json();
        setEntraStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch Entra stats:", err);
    }
  };

  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;

    setError("");
    setIsLoading(true);
    setActions([]);

    // Append user message to history
    const userMsg: Message = { sender: "user", text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    
    // Clear input field if sending the custom typed message
    if (textToSend === message) {
      setMessage("");
    }

    try {
      const res = await authFetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: textToSend,
          session_id: sessionId,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! Status: ${res.status}`);
      }


      const data = (await res.json()) as ChatResponse;

      // Update states
      if (data.session_id) {
        setSessionId(data.session_id);
      }
      if (data.category) {
        setCategory(data.category);
      }
      if (data.status) {
        setStatus(data.status);
      }
      if (data.actions) {
        setActions(data.actions);
      }
      if (data.ticket) {
        setActiveTicket(data.ticket);
        fetchTickets();
        fetchNotifications();
      }

      // Update approval states
      setApprovalRequired(data.approval_required || false);
      setApprovalStatus(data.approval_status || "PENDING");
      setRecommendedAction(data.recommended_action || "");
      setActionResult(data.action_result || null);
      
      // Dynamic updates for dashboards depending on role permissions
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

      // Append agent message to history
      const agentMsg: Message = { 
        sender: "agent", 
        text: data.response || data.question,
        category: data.category,
        source: data.source,
        context_used: data.context_used,
        action: data.action,
        tool_result: data.tool_result
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

  // 1. Render Glassmorphic Login screen if unauthenticated
  if (!user) {
    return (
      <main className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden font-sans">
        {/* Decorative background blur shapes */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
        
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 max-w-md w-full shadow-2xl relative z-10 space-y-6">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-extrabold text-white tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              Bridgestone IT Portal
            </h1>
            <p className="text-xs text-indigo-200/50 uppercase tracking-widest font-bold">
              Secure AI Support Agent
            </p>
          </div>

          {loginError && (
            <div className="p-3 bg-rose-500/15 border border-rose-500/20 text-rose-300 rounded-xl text-xs font-semibold text-center">
              ⚠️ {loginError}
            </div>
          )}

          <form onSubmit={(e) => { e.preventDefault(); handleLogin(usernameInput, passwordInput); }} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block">Username</label>
              <input
                type="text"
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
                placeholder="e.g. employee, manager, admin"
                className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block">Password</label>
              <input
                type="password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-white/5 border border-white/10 rounded-xl p-3 text-white text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                required
              />
            </div>

            <button
              type="submit"
              disabled={isLoggingIn}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-bold rounded-xl active:scale-95 transition-all shadow-lg shadow-indigo-900/30 cursor-pointer flex items-center justify-center gap-2"
            >
              {isLoggingIn ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Authenticating...</span>
                </>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          {/* Quick Demo Login Grid */}
          <div className="border-t border-white/10 pt-5 space-y-3">
            <span className="text-[10px] font-bold text-indigo-200/40 uppercase tracking-wider text-center block">Quick Demo Login</span>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => {
                  setUsernameInput("employee");
                  setPasswordInput("employeepassword");
                  handleLogin("employee", "employeepassword");
                }}
                className="py-2.5 px-1 bg-white/5 hover:bg-indigo-500/10 border border-white/10 hover:border-indigo-500/30 rounded-xl text-[10px] font-bold text-slate-300 transition-all cursor-pointer text-center"
              >
                👤 Employee
              </button>
              <button
                type="button"
                onClick={() => {
                  setUsernameInput("manager");
                  setPasswordInput("managerpassword");
                  handleLogin("manager", "managerpassword");
                }}
                className="py-2.5 px-1 bg-white/5 hover:bg-indigo-500/10 border border-white/10 hover:border-indigo-500/30 rounded-xl text-[10px] font-bold text-slate-300 transition-all cursor-pointer text-center"
              >
                👥 Manager
              </button>
              <button
                type="button"
                onClick={() => {
                  setUsernameInput("admin");
                  setPasswordInput("adminpassword");
                  handleLogin("admin", "adminpassword");
                }}
                className="py-2.5 px-1 bg-white/5 hover:bg-indigo-500/10 border border-white/10 hover:border-indigo-500/30 rounded-xl text-[10px] font-bold text-slate-300 transition-all cursor-pointer text-center"
              >
                🔒 Admin
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // 2. Render main application portal if authenticated
  return (
    <main className="min-h-screen bg-linear-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-4 font-sans">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-6xl w-full h-[650px]">
        
        {/* Left/Middle Columns: Chat Interface */}
        <div className="lg:col-span-2 bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-full transition-all duration-300">
          
          {/* Header */}
          <div className="p-5 border-b border-white/10 flex justify-between items-center bg-white/5">
            <div>
              <h1 className="text-2xl font-extrabold text-white tracking-tight bg-linear-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                Bridgestone IT Agent
              </h1>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-indigo-200/60 font-medium">
                  Conversational troubleshoot support
                </span>
                <span className="w-1 h-1 bg-white/20 rounded-full" />
                <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 border border-indigo-500/25 text-[9px] text-indigo-300 font-extrabold uppercase tracking-wider">
                  {user?.role}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {sessionId && (
                <button
                  onClick={startNewSession}
                  className="text-xs bg-white/5 hover:bg-white/10 text-slate-300 px-3 py-1.5 rounded-lg border border-white/10 transition-all font-semibold cursor-pointer"
                >
                  Reset Chat
                </button>
              )}
              <button
                onClick={handleLogout}
                className="text-xs bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 px-3 py-1.5 rounded-lg border border-rose-500/20 transition-all font-semibold cursor-pointer"
              >
                Sign Out
              </button>
            </div>
          </div>

          {/* Sub-header with Session info */}
          {sessionId && (
            <div className="px-5 py-2.5 bg-white/5 border-b border-white/10 flex flex-wrap justify-between gap-2 text-xs text-indigo-200/70 font-mono">
              <span>Session ID: {sessionId}</span>
              <span>Category: {category}</span>
            </div>
          )}

          {/* Chat Messages Panel */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
                <div className="p-4 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 animate-pulse text-2xl">
                  💬
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Hello, {user?.username}. How can IT support help you?</h3>
                  <p className="text-sm text-indigo-200/50 mt-1 max-w-md">
                    Type your issue (e.g. "VPN connection slow", "Outlook password lock") to start.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={index}
                  className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} animate-fadeIn`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md whitespace-pre-wrap ${
                      msg.sender === "user"
                        ? "bg-linear-to-r from-blue-600 to-indigo-600 text-white rounded-br-none"
                        : "bg-white/5 border border-white/10 text-indigo-100 rounded-bl-none"
                    }`}
                  >
                    <div className="text-[10px] opacity-60 font-semibold mb-1 uppercase tracking-wider">
                      {msg.sender === "user" ? "User" : "Agent"}
                    </div>
                    <div>
                      {msg.sender === "agent" && msg.action ? (
                        <div className="space-y-1.5">
                          <div>
                            <span className="opacity-60 block text-[10px] uppercase font-bold tracking-wider">Action:</span>
                            <span className="font-mono text-indigo-300 font-bold text-xs">{msg.action}</span>
                          </div>
                          <div className="border-t border-white/5 pt-1.5">
                            <span className="opacity-60 block text-[10px] uppercase font-bold tracking-wider">Response:</span>
                            <span className="text-sm text-indigo-100">{msg.text}</span>
                          </div>
                        </div>
                      ) : (
                        <>
                          <span className="font-semibold">{msg.sender === "user" ? `${user.username}: ` : "Agent: "}</span>
                          {msg.text}
                        </>
                      )}
                    </div>
                    {msg.sender === "agent" && msg.tool_result && (
                      <div className="mt-2.5 p-3 bg-slate-900/60 border border-indigo-500/30 rounded-xl text-xs font-mono space-y-1.5 backdrop-blur-xs">
                        <div className="flex justify-between items-center text-[10px] text-indigo-400 font-extrabold uppercase tracking-wider border-b border-indigo-500/10 pb-1.5 mb-1.5">
                          <span className="flex items-center gap-1">🔧 Tool Execution</span>
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[9px] border border-emerald-500/20 font-bold">
                            {msg.tool_result.status || "SUCCESS"}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] leading-relaxed">
                          <span className="text-indigo-200/50">Tool Name:</span>
                          <span className="text-indigo-300 font-semibold">{msg.tool_result.tool_name}</span>
                          {msg.tool_result.data && Object.entries(msg.tool_result.data).map(([key, val]) => (
                            <div key={key} className="contents">
                              <span className="text-indigo-200/50 capitalize">{key.replace(/_/g, ' ')}:</span>
                              <span className={`font-bold font-mono ${
                                val === "DISABLED" || val === "DENIED" || val === "OFFLINE" ? "text-rose-400" :
                                val === "ONLINE" || val === "ACTIVE" || val === "CONNECTED" || val === "ALLOWED" || val === true ? "text-emerald-400" :
                                "text-white"
                              }`}>{String(val)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {msg.sender === "agent" && msg.source && msg.source !== "N/A" && (
                      <div className="mt-2.5 pt-2 border-t border-white/10 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-indigo-300">
                        <span className="opacity-80">Category: <strong className="text-white">{msg.category}</strong></span>
                        <span className="opacity-80">Source: <strong className="text-white">{msg.source}</strong></span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-white/5 border border-white/10 text-indigo-200 rounded-2xl rounded-bl-none px-4 py-3 text-sm flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4 text-indigo-400" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Analyzing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Action Panel / Input Footer */}
          <div className="p-4 border-t border-white/10 bg-white/5 space-y-3">
            {approvalRequired && approvalStatus === "PENDING" && (
              <div className="p-4 rounded-xl bg-slate-900/80 border border-indigo-500/30 text-indigo-100 text-sm space-y-3 animate-fadeIn backdrop-blur-md">
                <div className="flex items-center justify-between border-b border-white/10 pb-2">
                  <span className="font-bold text-base text-indigo-300">
                     Recommended Action
                  </span>
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] border border-amber-500/30 font-bold uppercase tracking-wider">
                    Approval Required
                  </span>
                </div>
                <div className="text-sm">
                  The system recommends executing: <strong className="text-white font-mono">{recommendedAction}</strong>
                </div>
                <div className="flex gap-3 pt-1">
                  <button
                    onClick={() => sendMessage("yes")}
                    className="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl active:scale-95 transition-all cursor-pointer text-sm flex items-center justify-center gap-1.5 shadow-md shadow-emerald-900/30"
                  >
                     Approve
                  </button>
                  <button
                    onClick={() => sendMessage("no")}
                    className="flex-1 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-xl active:scale-95 transition-all cursor-pointer text-sm flex items-center justify-center gap-1.5 shadow-md shadow-rose-900/30"
                  >
                     Reject
                  </button>
                </div>
              </div>
            )}

            {actions.length > 0 && (
              <div className="flex gap-2 justify-center py-2">
                {actions.map((act) => (
                  <button
                    key={act}
                    onClick={() => sendMessage(act)}
                    className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl shadow-lg border border-indigo-500/20 active:scale-95 transition-all cursor-pointer text-sm"
                  >
                    {act === "SOLVED" ? "Solved" : act === "NOT_SOLVED" ? "Not Solved" : act}
                  </button>
                ))}
              </div>
            )}

            {error && (
              <div className="text-rose-400 text-xs font-semibold px-2 animate-pulse">
                ⚠️ {error}
              </div>
            )}

            {actions.length === 0 && (!approvalRequired || approvalStatus !== "PENDING") && (
              <div className="flex gap-2 items-end">
                <textarea
                  value={message}
                  onChange={(e) => {
                    setMessage(e.target.value);
                    if (error) setError("");
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage(message);
                    }
                  }}
                  disabled={isLoading}
                  placeholder={
                    sessionId 
                      ? "Type your response here..." 
                      : "Describe your IT issue (e.g. 'VPN disconnected')..."
                  }
                  className="flex-1 h-12 max-h-32 bg-white/5 border border-white/10 rounded-xl p-3 text-white text-sm placeholder-gray-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 resize-none disabled:opacity-50"
                />
                <button
                  onClick={() => sendMessage(message)}
                  disabled={isLoading || !message.trim()}
                  className="bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-40 disabled:pointer-events-none text-white p-3 rounded-xl shadow-lg transition-all duration-150 active:scale-95 flex items-center justify-center cursor-pointer h-12 w-12"
                >
                  <svg className="h-5 w-5 rotate-90 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Ticket Center & Recent History */}
        <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-full p-5 space-y-4">
          
          {/* Header */}
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">IT Service Desk</h2>
              <p className="text-xs text-indigo-200/50">Ticket assignment and resolution center</p>
            </div>
          </div>

          {/* Tab Selection Header (Admin Console restricted to ADMIN role) */}
          {user?.role === "ADMIN" ? (
            <div className="flex bg-white/5 p-1 rounded-lg border border-white/10">
              <button
                onClick={() => setActiveRightTab("service_desk")}
                className={`flex-1 text-center py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  activeRightTab === "service_desk"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-indigo-200/60 hover:text-indigo-100"
                }`}
              >
                Service Desk
              </button>
              <button
                onClick={() => setActiveRightTab("admin_dashboard")}
                className={`flex-1 text-center py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  activeRightTab === "admin_dashboard"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-indigo-200/60 hover:text-indigo-100"
                }`}
              >
                Admin Console
              </button>
              <button
                onClick={() => setActiveRightTab("monitoring")}
                className={`flex-1 text-center py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                  activeRightTab === "monitoring"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-indigo-200/60 hover:text-indigo-100"
                }`}
              >
                Monitoring
              </button>
            </div>
          ) : (
            <div className="py-2 border-b border-white/5 text-center text-xs font-bold text-indigo-300 uppercase tracking-wider bg-white/5 rounded-lg">
              Support Dashboard
            </div>
          )}

          {activeRightTab === "service_desk" || user?.role !== "ADMIN" ? (
            <div className="flex-1 flex flex-col min-h-0 space-y-4 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-white/10">
              {/* Active Ticket / Resolution Notifications */}
              {status === "RESOLVED" && (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 text-sm animate-fadeIn">
                  <span className="font-bold block text-base mb-1">Issue Resolved Successfully</span>
                  We have closed the conversation. Let us know if you need anything else!
                </div>
              )}

              {activeTicket && (
                <div className="p-4 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-100 text-sm space-y-2.5 animate-fadeIn">
                  <span className="font-bold block text-indigo-300 text-base border-b border-white/10 pb-1.5">
                    Ticket Created Successfully
                  </span>
                  <div className="grid grid-cols-2 gap-y-1.5 text-xs font-medium">
                    <span className="text-indigo-200/50">Ticket ID:</span>
                    <span className="font-mono font-bold text-indigo-300">{activeTicket.ticket_id}</span>
                    
                    {activeTicket.servicenow_id && (
                      <>
                        <span className="text-indigo-200/50">ServiceNow ID:</span>
                        <span className="font-mono font-bold text-amber-400">{activeTicket.servicenow_id}</span>
                      </>
                    )}
                    
                    <span className="text-indigo-200/50">Assigned Team:</span>
                    <span>{activeTicket.assigned_team}</span>
                    
                    <span className="text-indigo-200/50">Status:</span>
                    <span className="font-semibold text-emerald-400">{activeTicket.status}</span>

                    {activeTicket.priority && (
                      <>
                        <span className="text-indigo-200/50">Priority:</span>
                        <span className={`font-semibold ${
                          activeTicket.priority === "CRITICAL" ? "text-rose-400 font-extrabold" :
                          activeTicket.priority === "HIGH" ? "text-amber-400 font-bold" :
                          activeTicket.priority === "MEDIUM" ? "text-yellow-300" : "text-emerald-400"
                        }`}>{activeTicket.priority}</span>
                      </>
                    )}

                    {activeTicket.sla_hours !== undefined && (
                      <>
                        <span className="text-indigo-200/50">SLA Target:</span>
                        <span className="font-semibold text-indigo-300">
                          {activeTicket.sla_hours} {activeTicket.sla_hours === 1 ? "Hour" : "Hours"}
                        </span>
                      </>
                    )}
                  </div>
                </div>
              )}

              {actionResult && (
                <div className="p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-100 text-sm space-y-2.5 animate-fadeIn">
                  <span className="font-bold block text-emerald-300 text-base border-b border-white/10 pb-1.5">
                    Request Created Successfully
                  </span>
                  <div className="grid grid-cols-2 gap-y-1.5 text-xs font-medium">
                    <span className="text-emerald-200/50">Request ID:</span>
                    <span className="font-mono font-bold text-emerald-300">{actionResult.request_id}</span>
                    
                    <span className="text-emerald-200/50">ServiceNow ID:</span>
                    <span className="font-mono font-bold text-amber-400">{actionResult.servicenow_id}</span>
                    
                    <span className="text-emerald-200/50">Action Type:</span>
                    <span className="font-mono">{actionResult.action_type}</span>
                    
                    <span className="text-emerald-200/50">Status:</span>
                    <span className="font-semibold text-emerald-400">{actionResult.status}</span>
                  </div>
                </div>
              )}

              {/* Recent Tickets List */}
              <div className="flex-[2] flex flex-col min-h-0">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2.5">
                  Recent Tickets ({tickets.length})
                </h3>
                
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-white/10 max-h-48">
                  {tickets.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic py-4">No tickets recorded</p>
                  ) : (
                    tickets.slice().reverse().map((t) => (
                      <div 
                        key={t.ticket_id}
                        className="p-3 bg-white/5 border border-white/5 hover:border-indigo-500/20 rounded-xl flex items-center justify-between text-xs transition-all mb-2"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-indigo-200">{t.ticket_id}</span>
                            {t.servicenow_id && (
                              <span className="font-mono text-[10px] bg-amber-500/10 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">
                                {t.servicenow_id}
                              </span>
                            )}
                          </div>
                          <span className="block text-[10px] text-indigo-200/40">{t.category}</span>
                          <div className="flex gap-2 items-center mt-1">
                            {t.priority && (
                              <span className={`text-[10px] font-bold ${
                                t.priority === "CRITICAL" ? "text-rose-400" :
                                t.priority === "HIGH" ? "text-amber-400" :
                                t.priority === "MEDIUM" ? "text-yellow-300" : "text-emerald-400"
                              }`}>
                                {t.priority}
                              </span>
                            )}
                            {t.sla_hours !== undefined && (
                              <span className="text-[10px] text-indigo-200/40 font-semibold">
                                SLA: {t.sla_hours}h
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="text-right space-y-1">
                          <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 font-semibold border border-indigo-500/10">
                            {t.status}
                          </span>
                          <span className="block text-[10px] text-indigo-200/40">{t.assigned_team}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Recent Actions List (Visible only to Manager/Admin) */}
              {(user?.role === "ADMIN" || user?.role === "MANAGER") && (
                <div className="flex-[2] flex flex-col min-h-0 border-t border-white/10 pt-3">
                  <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2.5">
                    Recent Actions ({actionsHistory.length})
                  </h3>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-white/10 max-h-36">
                    {actionsHistory.length === 0 ? (
                      <p className="text-xs text-indigo-200/30 italic py-4">No actions executed</p>
                    ) : (
                      actionsHistory.slice().reverse().map((act) => (
                        <div 
                          key={act.request_id}
                          className="p-3 bg-white/5 border border-white/5 hover:border-indigo-500/20 rounded-xl flex items-center justify-between text-xs transition-all mb-2"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono font-bold text-indigo-200">{act.request_id}</span>
                              {act.servicenow_id && (
                                <span className="font-mono text-[10px] bg-amber-500/10 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">
                                  {act.servicenow_id}
                                </span>
                              )}
                            </div>
                            <span className="block text-[10px] text-indigo-200/40">{act.action_type}</span>
                          </div>
                          <div className="text-right space-y-1">
                            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 font-semibold border border-emerald-500/10">
                              {act.status}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {/* Recent Notifications List */}
              <div className="flex-[2] flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  Recent Notifications ({notifications.length})
                </h3>
                
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-white/10 max-h-36">
                  {notifications.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic py-3">No notifications recorded</p>
                  ) : (
                    notifications.slice().reverse().map((n) => (
                      <div 
                        key={n.notification_id}
                        className="p-2.5 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1 mb-2"
                      >
                        <div className="flex justify-between items-center text-[10px] text-indigo-300 font-semibold uppercase tracking-wider">
                          <span className="font-mono">{n.notification_id}</span>
                          <span className="opacity-75">{n.recipient}</span>
                        </div>
                        <p className="text-indigo-100/90 text-xs leading-normal">{n.message}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : activeRightTab === "admin_dashboard" ? (
            // Admin Console View (Protected & visible only to ADMIN role)
            <div className="flex-1 flex flex-col min-h-0 space-y-4 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-white/10">
              
              {/* Recent Audit Logs */}
              <div className="flex flex-col min-h-0">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  Audit Events ({auditLogs.length})
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {auditLogs.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic">No audit records</p>
                  ) : (
                    auditLogs.slice().reverse().map((log, idx) => (
                      <div key={idx} className="p-2.5 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1 mb-1">
                        <div className="flex justify-between items-center text-[10px] text-indigo-400">
                          <span className="font-mono">{log.session_id.substring(0, 8)}...</span>
                          <span>{log.category}</span>
                        </div>
                        <p className="text-white font-medium">"{log.user_message}"</p>
                        <div className="flex justify-between items-center text-[10px] text-indigo-200/50 pt-1 border-t border-white/5">
                          <span>Decision: <strong className="text-indigo-300">{log.decision}</strong></span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                            log.approval_status === "APPROVED" ? "bg-emerald-500/10 text-emerald-400" :
                            log.approval_status === "REJECTED" ? "bg-rose-500/10 text-rose-400" :
                            "bg-amber-500/10 text-amber-400"
                          }`}>{log.approval_status}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Action History */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  Action History ({actionsHistory.length})
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {actionsHistory.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic">No action history logs</p>
                  ) : (
                    actionsHistory.slice().reverse().map((act, idx) => (
                      <div key={idx} className="p-2.5 bg-white/5 border border-white/5 rounded-xl text-xs flex justify-between items-center mb-1">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-indigo-200">{act.request_id}</span>
                            <span className="text-[10px] bg-amber-500/10 text-amber-300 px-1 rounded">{act.servicenow_id}</span>
                          </div>
                          <span className="block text-[10px] text-indigo-200/40">{act.action_type}</span>
                        </div>
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold text-[9px]">{act.status}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Approval History */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  Approval History ({approvals.length})
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {approvals.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic">No approvals recorded</p>
                  ) : (
                    approvals.slice().reverse().map((app, idx) => (
                      <div key={idx} className="p-2.5 bg-white/5 border border-white/5 rounded-xl text-xs flex justify-between items-center mb-1">
                        <div>
                          <span className="font-mono text-indigo-200 text-[11px] block">{app.recommended_action}</span>
                          <span className="text-[9px] text-indigo-200/30 font-mono">{app.session_id.substring(0, 8)}...</span>
                        </div>
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                          app.approval_status === "APPROVED" ? "bg-emerald-500/10 text-emerald-400" :
                          app.approval_status === "REJECTED" ? "bg-rose-500/10 text-rose-400" :
                          "bg-amber-500/10 text-amber-400"
                        }`}>{app.approval_status}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Security Logs (Admin only) */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-rose-400 uppercase tracking-wider mb-2">
                  Security Event Logs ({securityLogs.length})
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {securityLogs.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic">No security events logged</p>
                  ) : (
                    securityLogs.slice().reverse().map((log, idx) => (
                      <div key={idx} className="p-2 bg-white/5 border border-white/5 rounded-xl text-[10px] space-y-1 mb-1">
                        <div className="flex justify-between items-center text-[9px] text-rose-300 font-bold uppercase">
                          <span>{log.event_type}</span>
                          <span className="opacity-40">{log.timestamp.substring(11, 19)}</span>
                        </div>
                        <p className="text-indigo-100 font-mono text-[10px] leading-tight">{log.details}</p>
                        {log.username && (
                          <div className="text-[9px] text-indigo-200/40 font-semibold pt-0.5">
                            User: <strong className="text-indigo-200">{log.username}</strong>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Agent Traces */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  Agent Traces ({agentTraces.length})
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {agentTraces.length === 0 ? (
                    <p className="text-xs text-indigo-200/30 italic">No agent traces logged</p>
                  ) : (
                    agentTraces.slice().reverse().map((tr, idx) => (
                      <div key={idx} className="p-2.5 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1 mb-1">
                        <div className="flex justify-between items-center text-[10px] text-indigo-300 font-bold uppercase">
                          <span>{tr.agent_name}</span>
                          <span className="opacity-40 font-mono">{tr.session_id.substring(0, 8)}...</span>
                        </div>
                        <pre className="p-1.5 bg-slate-950/60 rounded text-[9px] text-indigo-200 font-mono overflow-x-auto border border-white/5 whitespace-pre-wrap leading-tight">
                          {JSON.stringify(tr.output, null, 2)}
                        </pre>
                      </div>
                    ))
                  )}
                </div>
              </div>

            </div>
          ) : (
            // Monitoring Tab View (Protected & visible only to ADMIN role)
            <div className="flex-1 flex flex-col min-h-0 space-y-4 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-white/10">
              
              {/* Section 1: Core System Status */}
              <div className="flex flex-col min-h-0">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2.5">
                  Core System Health
                </h3>
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl text-center space-y-1">
                    <span className="text-[10px] text-indigo-200/50 block font-bold uppercase tracking-wider">Database</span>
                    <div className="flex items-center justify-center gap-1.5 mt-1">
                      <span className={`w-2.5 h-2.5 rounded-full ${systemStatus?.database === "healthy" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                      <span className="text-xs font-bold text-white uppercase">{systemStatus?.database || "checking..."}</span>
                    </div>
                  </div>
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl text-center space-y-1">
                    <span className="text-[10px] text-indigo-200/50 block font-bold uppercase tracking-wider">Redis</span>
                    <div className="flex items-center justify-center gap-1.5 mt-1">
                      <span className={`w-2.5 h-2.5 rounded-full ${systemStatus?.redis === "healthy" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                      <span className="text-xs font-bold text-white uppercase">{systemStatus?.redis || "checking..."}</span>
                    </div>
                  </div>
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl text-center space-y-1">
                    <span className="text-[10px] text-indigo-200/50 block font-bold uppercase tracking-wider">Gemini LLM</span>
                    <div className="flex items-center justify-center gap-1.5 mt-1">
                      <span className={`w-2.5 h-2.5 rounded-full ${systemStatus?.gemini === "healthy" ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                      <span className="text-xs font-bold text-white uppercase">{systemStatus?.gemini === "healthy" ? "HEALTHY" : systemStatus?.gemini || "checking..."}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 2: Enterprise Adapters */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2.5">
                  Enterprise Adapters
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  {systemStatus?.adapters ? (
                    Object.entries(systemStatus.adapters).map(([name, status]: [string, any]) => {
                      const isOnline = typeof status === "object" ? status?.status === "healthy" : status === "healthy";
                      const latency = typeof status === "object" ? status?.latency : null;
                      return (
                        <div key={name} className="p-2.5 bg-white/5 border border-white/5 rounded-xl flex flex-col space-y-1 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-indigo-200">{name}</span>
                            <div className="flex items-center gap-1.5">
                              <span className={`w-2 h-2 rounded-full ${isOnline ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                              <span className="font-mono text-[10px] font-bold text-white uppercase">{isOnline ? "online" : "offline"}</span>
                            </div>
                          </div>
                          {latency !== null && latency !== undefined && (
                            <div className="flex justify-between items-center text-[10px] text-indigo-300 font-mono border-t border-white/5 pt-1 mt-1">
                              <span>Latency:</span>
                              <span>{(latency * 1000).toFixed(0)} ms</span>
                            </div>
                          )}
                          {(name === "Microsoft Graph" || name === "Active Directory") && typeof status === "object" && status?.token_expiry && (
                            <div className="text-[9px] text-indigo-200/50 font-mono mt-1 pt-1 border-t border-white/5 flex justify-between">
                              <span>Token:</span>
                              <span className="text-emerald-400 font-bold">ACTIVE</span>
                            </div>
                          )}
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-xs text-indigo-200/30 italic py-2 col-span-2">Checking adapters...</p>
                  )}
                </div>
              </div>

              {/* Section 3: Live System Metrics Counters */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2.5">
                  Operational Metrics
                </h3>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl space-y-1">
                    <span className="text-[10px] text-indigo-200/40 font-bold block uppercase tracking-wider">Tickets Created</span>
                    <span className="text-lg font-mono font-bold text-indigo-300">{tickets.length}</span>
                  </div>
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl space-y-1">
                    <span className="text-[10px] text-indigo-200/40 font-bold block uppercase tracking-wider">Actions Executed</span>
                    <span className="text-lg font-mono font-bold text-emerald-400">{actionsHistory.length}</span>
                  </div>
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl space-y-1">
                    <span className="text-[10px] text-indigo-200/40 font-bold block uppercase tracking-wider">Pending Approvals</span>
                    <span className="text-lg font-mono font-bold text-amber-400">
                      {approvals.filter(a => a.approval_status === "PENDING").length}
                    </span>
                  </div>
                  <div className="p-3 bg-white/5 border border-white/5 rounded-xl space-y-1">
                    <span className="text-[10px] text-indigo-200/40 font-bold block uppercase tracking-wider">Security Events</span>
                    <span className="text-lg font-mono font-bold text-rose-400">{securityLogs.length}</span>
                  </div>
                </div>
              </div>

              {/* Section 4: Alert Notifications / Incidents */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider mb-2">
                  System Alerts
                </h3>
                <div className="space-y-2 max-h-36 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                  {systemStatus?.status === "unhealthy" && (
                    <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs font-semibold font-mono">
                      🚨 Critical: Core platform services are unreachable. IT Support Agent offline.
                    </div>
                  )}
                  {systemStatus?.status === "degraded" && (
                    <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-xl text-xs font-semibold font-mono">
                      ⚠️ Warning: Core components degraded. Some adapters are offline.
                    </div>
                  )}
                  {systemStatus?.database === "unhealthy" && (
                    <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs font-semibold font-mono">
                      [Alert] DatabaseDown: SQL connection actively failing.
                    </div>
                  )}
                  {systemStatus?.redis === "unhealthy" && (
                    <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded-xl text-xs font-semibold font-mono">
                      [Alert] RedisDown: Cache connection failed, falling back to DB.
                    </div>
                  )}
                  {securityLogs.filter(l => l.event_type === "FAILED_LOGIN").length > 5 && (
                    <div className="p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs font-semibold font-mono">
                      [Alert] AuthFailureSpike: Excessive failed login attempts detected.
                    </div>
                  )}
                  {systemStatus?.status === "healthy" && securityLogs.filter(l => l.event_type === "FAILED_LOGIN").length <= 5 && (
                    <div className="p-2.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 rounded-xl text-xs font-semibold text-center">
                      ✓ All systems operational. No active alerts.
                    </div>
                  )}
                </div>
              </div>

              {/* Section 5: ServiceNow Integration Monitoring */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <div className="flex justify-between items-center mb-2.5">
                  <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">
                    ServiceNow Active Monitoring
                  </h3>
                  <div className="text-[10px] text-indigo-200/50 font-mono">
                    Incidents: {servicenowIncidents.length} | Requests: {servicenowRequests.length}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Incidents Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Incidents</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {servicenowIncidents.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No incidents synced</p>
                      ) : (
                        servicenowIncidents.slice().reverse().map((inc) => (
                          <div key={inc.sys_id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200 font-mono">{inc.number}</span>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                inc.state === "CLOSED" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/20" : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/20"
                              }`}>
                                {inc.state}
                              </span>
                            </div>
                            <div className="text-[10px] text-indigo-200/70 truncate">{inc.description}</div>
                            <div className="flex justify-between items-center text-[9px] text-indigo-200/40">
                              <span>Cat: {inc.category}</span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Requests Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Catalog Requests</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {servicenowRequests.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No requests synced</p>
                      ) : (
                        servicenowRequests.slice().reverse().map((req) => (
                          <div key={req.sys_id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200 font-mono">{req.number}</span>
                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                req.state === "CLOSED" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/20" : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/20"
                              }`}>
                                {req.state}
                              </span>
                            </div>
                            <div className="text-[10px] text-indigo-200/70 truncate">{req.description}</div>
                            <div className="flex justify-between items-center text-[9px] text-indigo-200/40">
                              <span>Action: {req.action_type}</span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 6: Microsoft Graph Active Monitoring */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <div className="flex justify-between items-center mb-2.5">
                  <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">
                    Microsoft Graph Active Monitoring
                  </h3>
                  <div className="text-[10px] text-indigo-200/50 font-mono">
                    Users: {graphUsers.length} | Groups: {graphGroups.length}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Users Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Users Directory</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {graphUsers.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No users synced</p>
                      ) : (
                        graphUsers.map((gusr) => (
                          <div key={gusr.id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200">{gusr.displayName}</span>
                              <span className="text-[9px] text-indigo-300/80 font-mono">{gusr.jobTitle || "User"}</span>
                            </div>
                            <div className="text-[10px] text-indigo-200/70 truncate">{gusr.userPrincipalName}</div>
                            {gusr.officeLocation && (
                              <div className="text-[9px] text-indigo-200/40">Loc: {gusr.officeLocation}</div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Groups Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Directory Groups</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {graphGroups.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No groups synced</p>
                      ) : (
                        graphGroups.map((ggrp) => (
                          <div key={ggrp.id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200">{ggrp.displayName}</span>
                              <span className="text-[9px] text-emerald-400 font-mono font-bold uppercase">Security</span>
                            </div>
                            {ggrp.description && (
                              <div className="text-[10px] text-indigo-200/70 truncate">{ggrp.description}</div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Section 7: Azure AD / Entra ID Active Monitoring */}
              <div className="flex flex-col min-h-0 border-t border-white/10 pt-3">
                <div className="flex justify-between items-center mb-2.5">
                  <h3 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">
                    Azure AD / Entra ID Active Monitoring
                  </h3>
                  <div className="text-[10px] text-indigo-200/50 font-mono">
                    Users: {entraUsers.length} | Groups: {entraGroups.length}
                  </div>
                </div>

                {entraStats && (
                  <div className="grid grid-cols-3 gap-2 mb-3 text-[10px]">
                    <div className="p-2 bg-white/5 border border-white/5 rounded-xl text-center space-y-0.5">
                      <span className="text-[9px] text-indigo-200/40 font-bold block uppercase tracking-wider">Group Checks</span>
                      <span className="font-mono font-bold text-indigo-300 block text-xs">{entraStats.group_membership_checks}</span>
                    </div>
                    <div className="p-2 bg-white/5 border border-white/5 rounded-xl text-center space-y-0.5">
                      <span className="text-[9px] text-indigo-200/40 font-bold block uppercase tracking-wider">Access Checks</span>
                      <span className="font-mono font-bold text-emerald-400 block text-xs">{entraStats.access_validation_checks}</span>
                    </div>
                    <div className="p-2 bg-white/5 border border-white/5 rounded-xl text-center space-y-0.5">
                      <span className="text-[9px] text-indigo-200/40 font-bold block uppercase tracking-wider">Role Checks</span>
                      <span className="font-mono font-bold text-amber-400 block text-xs">{entraStats.role_assignment_checks}</span>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  {/* Users Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Users Directory</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {entraUsers.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No users synced</p>
                      ) : (
                        entraUsers.map((eusr) => (
                          <div key={eusr.id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200">{eusr.displayName}</span>
                              <span className="text-[9px] text-indigo-300/80 font-mono">{eusr.department || "IT"}</span>
                            </div>
                            <div className="text-[10px] text-indigo-200/70 truncate">{eusr.userPrincipalName}</div>
                            {eusr.jobTitle && (
                              <div className="text-[9px] text-indigo-200/40">Title: {eusr.jobTitle}</div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Groups Column */}
                  <div className="flex flex-col min-h-0 space-y-2">
                    <span className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider mb-1">Directory Groups</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 pr-1">
                      {entraGroups.length === 0 ? (
                        <p className="text-xs text-indigo-200/30 italic">No groups synced</p>
                      ) : (
                        entraGroups.map((egrp) => (
                          <div key={egrp.id} className="p-2 bg-white/5 border border-white/5 rounded-xl text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className="font-bold text-indigo-200">{egrp.displayName}</span>
                              <span className="text-[9px] text-emerald-400 font-mono font-bold uppercase">Security</span>
                            </div>
                            {egrp.description && (
                              <div className="text-[10px] text-indigo-200/70 truncate">{egrp.description}</div>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

        </div>
      </div>
    </main>
  );
}