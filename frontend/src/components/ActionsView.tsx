"use client";


import { apiFetch, NetworkError } from "@/lib/apiClient";
import { useState, useEffect, useCallback } from "react";
import {
  Power, Mail, Users, Database, Wifi, Printer, Settings, Shield, Activity,
  KeyRound, Package, RefreshCw, Terminal, Cloud, Server, HardDrive, Trash2, Cpu,
  Sliders, Lock, CheckCircle2, AlertTriangle, Play, Clock, ArrowRight, Loader2,
  FileText, Check, ChevronDown, ChevronUp, History, Info, AlertCircle
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

interface ActionsViewProps {
  user: any;
  token: string | null;
  apiBaseUrl: string;
}

interface ActionCardInfo {
  action_name: string;
  description: string;
  approval_required: "NONE" | "MANAGER" | "ADMIN";
  approved_for_user: boolean;
}

interface HistoryRecord {
  id: number;
  timestamp: string;
  username: string;
  device_id: string;
  action_name: string;
  result: "SUCCESS" | "FAILED" | "PENDING_APPROVAL" | "REJECTED";
  duration: number;
  logs: string;
}

const ACTION_ICONS: Record<string, any> = {
  "Restart Computer": Power,
  "Restart Outlook": Mail,
  "Restart Teams": Users,
  "Flush DNS": Database,
  "Renew IP": Wifi,
  "Clear Print Queue": Printer,
  "Restart Print Spooler": Settings,
  "Connect VPN": Shield,
  "Disconnect VPN": Shield,
  "Network Diagnostics": Activity,
  "BitLocker Recovery": KeyRound,
  "Install Approved Software": Package,
  "Update Approved Software": RefreshCw,
  "Restart Windows Explorer": Terminal,
  "Sync OneDrive": Cloud,
  "Open Software Center": Server,
  "Map Network Drive": HardDrive,
  "Clear Temp Files": Trash2,
  "System Information": Cpu,
  "SAP Installation": Package
};

const ACTION_KEYS: Record<string, string> = {
  "Restart Computer": "restart_pc",
  "Restart Outlook": "restart_outlook",
  "Restart Teams": "restart_teams",
  "Flush DNS": "flush_dns",
  "Renew IP": "renew_ip",
  "Clear Print Queue": "clear_print_queue",
  "Restart Print Spooler": "restart_print_spooler",
  "Connect VPN": "connect_vpn",
  "Disconnect VPN": "disconnect_vpn",
  "Network Diagnostics": "network_diagnostics",
  "BitLocker Recovery": "bitlocker_recovery",
  "Install Approved Software": "install_approved_software",
  "Update Approved Software": "update_approved_software",
  "Restart Windows Explorer": "restart_windows_explorer",
  "Sync OneDrive": "sync_onedrive",
  "Open Software Center": "open_software_center",
  "Map Network Drive": "map_network_drive",
  "Clear Temp Files": "clear_temp_files",
  "System Information": "system_information",
  "SAP Installation": "sap_installation"
};

export default function ActionsView({ user, token, apiBaseUrl }: ActionsViewProps) {
  const [actions, setActions] = useState<ActionCardInfo[]>([]);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  // Device Agent Status states
  const [agentOnline, setAgentOnline] = useState<boolean>(false);
  const [agentVersion, setAgentVersion] = useState<string>("v1.2.4");
  const [hostname, setHostname] = useState<string>("BS-EMP-WS09");
  const [operatingSystem, setOperatingSystem] = useState<string>("Windows 11 Enterprise (Build 22631)");
  const [lastHeartbeat, setLastHeartbeat] = useState<string>("Never");

  // Search and Category filters
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<"ALL" | "NONE" | "APPROVAL">("ALL");

  // Selected execution result modal
  const [activeExecResult, setActiveExecResult] = useState<any | null>(null);

  // Expanded card logs
  const [expandedLogs, setExpandedLogs] = useState<Record<string, boolean>>({});

  // Confirmation Modal
  const [confirmingAction, setConfirmingAction] = useState<ActionCardInfo | null>(null);

  // Toast notifications
  const [toast, setToast] = useState<{ msg: string; type: "success" | "error" } | null>(null);

  const showToast = (msg: string, type: "success" | "error" = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const getAuthHeaders = useCallback(() => ({
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  }), [token]);

  // Fetch agent health and system info
  const checkAgentStatus = async () => {
    try {
      const resHealth = await apiFetch(`${apiBaseUrl}/api/device-agent/health`, { headers: getAuthHeaders() });
      if (resHealth.ok) {
        const healthData = await resHealth.json();
        if (healthData.success !== false) {
          setAgentOnline(true);
          setLastHeartbeat(new Date().toLocaleString());
          if (healthData.version) setAgentVersion(healthData.version);
        } else {
          setAgentOnline(false);
        }
      } else {
        setAgentOnline(false);
      }

      const resInfo = await apiFetch(`${apiBaseUrl}/api/device-agent/system-info`, { headers: getAuthHeaders() });
      if (resInfo.ok) {
        const infoData = await resInfo.json();
        if (infoData.success !== false) {
          if (infoData.hostname) setHostname(infoData.hostname);
          if (infoData.os) setOperatingSystem(infoData.os);
        }
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      setAgentOnline(false);
    }
  };

  // Fetch actions and history
  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      await checkAgentStatus();

      const resList = await apiFetch(`${apiBaseUrl}/api/it-actions/list`, { headers: getAuthHeaders() });
      if (resList.ok) {
        const data = await resList.json();
        setActions(data.actions || []);
      }

      const resHist = await apiFetch(`${apiBaseUrl}/api/it-actions/history`, { headers: getAuthHeaders() });
      if (resHist.ok) {
        const data = await resHist.json();
        setHistory(data.history || []);
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network error pulling actions data", "error");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, getAuthHeaders]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Execute device action
  const handleExecute = async (action: ActionCardInfo) => {
    setConfirmingAction(null);
    setExecutingAction(action.action_name);

    const actionKey = ACTION_KEYS[action.action_name] || "generic_action";

    try {
      const res = await apiFetch(`${apiBaseUrl}/api/device-agent/action`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          action: actionKey,
          parameters: {}
        })
      });
      const data = await res.json();
      if (res.ok) {
        if (data.success) {
          showToast(`✓ Action '${action.action_name}' run successfully`, "success");
        } else {
          showToast(`✗ Execution failed: ${data.message}`, "error");
        }
        setActiveExecResult({
          action_name: action.action_name,
          duration: data.duration_ms ? round(data.duration_ms / 1000, 2) : 0,
          logs: data.logs && data.logs.length > 0 ? data.logs.join("\n") : data.message || "Execution logs empty"
        });
        loadData(true);
      } else {
        showToast(data.detail || "Execution failed", "error");
      }
    } catch (e) {
      if (e instanceof NetworkError) return; // silently skip when backend offline
      showToast("Network error executing action", "error");
    } finally {
      setExecutingAction(null);
    }
  };

  const round = (val: number, decimals: number) => {
    return Number(Math.round(Number(val + "e" + decimals)) + "e-" + decimals);
  };

  const filteredActions = actions.filter(act => {
    const matchesSearch = act.action_name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          act.description.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (filterType === "NONE") {
      return matchesSearch && act.approval_required === "NONE";
    } else if (filterType === "APPROVAL") {
      return matchesSearch && act.approval_required !== "NONE";
    }
    return matchesSearch;
  });

  const toggleLogs = (name: string) => {
    setExpandedLogs(prev => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="flex-1 flex flex-col bg-[#F8FAFC] font-sans overflow-y-auto">
      {/* Toast Notification */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-2.5 px-4 py-3 rounded-xl shadow-xl text-xs font-bold border transition-all animate-bounce
          ${toast.type === "success" 
            ? "bg-green-50 text-green-800 border-green-200" 
            : "bg-red-50 text-red-800 border-red-200"}`}>
          {toast.type === "success" ? <CheckCircle2 className="w-4 h-4 text-[#16A34A]" /> : <AlertTriangle className="w-4 h-4 text-red-600" />}
          {toast.msg}
        </div>
      )}

      {/* Page Header */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 flex-shrink-0">
        <div>
          <h1 className="text-xs font-black text-[#0F172A] uppercase tracking-wider flex items-center gap-2">
            <Terminal className="w-5 h-5 text-[#E30613]" />
            IT Actions Center
          </h1>
          <p className="text-[10px] text-[#64748B] font-bold mt-1 uppercase tracking-wider">Execute approved automated tasks directly on your workstation.</p>
        </div>

        <button
          onClick={() => loadData(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl text-xs font-bold text-[#475569] cursor-pointer shadow-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Status
        </button>
      </div>

      <div className="flex-1 p-6 space-y-6 max-w-7xl w-full mx-auto">
        
        {/* Device Agent Status Board */}
        <div className="bg-white border border-[#E2E8F0] p-5 rounded-2xl shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2.5">
            <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider flex items-center gap-2">
              <Cpu className="w-4.5 h-4.5 text-[#E30613]" />
              Enterprise Device Agent Gateway Status
            </span>
            <span className={`px-3 py-1 rounded-full border text-[10px] font-bold flex items-center gap-1.5 ${
              agentOnline 
                ? "bg-green-50 text-green-705 border-green-200" 
                : "bg-red-50 text-red-705 border-red-200"
            }`}>
              <span className={`w-2 h-2 rounded-full ${agentOnline ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
              {agentOnline ? "ONLINE / CONNECTED" : "OFFLINE / DISCONNECTED"}
            </span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-bold uppercase tracking-wider">
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl">
              <span className="text-[9px] text-[#64748B] block">Host Computer Name</span>
              <span className="font-mono text-[#1E293B] block mt-0.5">{hostname}</span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl font-semibold">
              <span className="text-[9px] text-[#64748B] block font-bold">Operating System</span>
              <span className="text-[#1E293B] block mt-0.5 normal-case font-bold">{operatingSystem}</span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl font-mono">
              <span className="text-[9px] text-[#64748B] block font-bold font-sans">Agent Version</span>
              <span className="text-[#1E293B] block mt-0.5">{agentVersion}</span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-3 rounded-xl font-semibold">
              <span className="text-[9px] text-[#64748B] block font-bold font-sans">Last Heartbeat</span>
              <span className="text-[#1E293B] block mt-0.5 normal-case font-bold">{lastHeartbeat}</span>
            </div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="w-full sm:max-w-xs">
            <SearchInput
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search available actions..."
            />
          </div>

          <div className="flex gap-2">
            {[
              { id: "ALL", label: "All Actions" },
              { id: "NONE", label: "No Approval Required" },
              { id: "APPROVAL", label: "Approval Required" },
            ].map(type => (
              <button
                key={type.id}
                onClick={() => setFilterType(type.id as any)}
                className={`px-3 py-1.5 rounded-xl border text-xs font-bold cursor-pointer transition-all shadow-xs
                  ${filterType === type.id 
                    ? "bg-[#FEF2F2] text-[#E30613] border-[#FCA5A5]" 
                    : "bg-white border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#475569]"}`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="h-60 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-[#E30613] animate-spin" />
            <span className="text-xs text-[#64748B] font-bold uppercase tracking-wider">Retrieving catalog info...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredActions.map(act => {
              const Icon = ACTION_ICONS[act.action_name] || Terminal;
              const isApproved = act.approved_for_user;
              const isExec = executingAction === act.action_name;
              const hasLogs = history.some(h => h.action_name === act.action_name);

              return (
                <div 
                  key={act.action_name} 
                  className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs hover:scale-[1.01] transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <div className="w-9 h-9 rounded-xl bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center">
                        <Icon className="w-5 h-5 text-[#E30613]" />
                      </div>
                      <StatusPill status={act.approval_required === "NONE" ? "SUCCESS" : "PENDING_APPROVAL"} />
                    </div>

                    {/* Content */}
                    <div>
                      <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">{act.action_name}</h3>
                      <p className="text-[11px] text-[#475569] font-semibold mt-1 leading-normal">{act.description}</p>
                    </div>

                    <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl text-[10px] space-y-1 font-bold">
                      <div className="flex justify-between text-[#64748B] uppercase tracking-wider">
                        <span>Pre-requisites:</span>
                        <span className="text-[#334155]">Device Agent Connect</span>
                      </div>
                      <div className="flex justify-between text-[#64748B] uppercase tracking-wider">
                        <span>Auth State:</span>
                        <span className={`uppercase ${isApproved ? "text-[#16A34A]" : "text-amber-600"}`}>
                          {isApproved ? "Authorized ✓" : "Restricted ⚠"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-[#E2E8F0] space-y-3">
                    {hasLogs && (
                      <button
                        onClick={() => toggleLogs(act.action_name)}
                        className="w-full flex items-center justify-between text-[10px] font-bold text-[#64748B] hover:text-[#475569] cursor-pointer uppercase tracking-wider"
                      >
                        <span className="flex items-center gap-1.5">
                          <History className="w-3.5 h-3.5" />
                          View Local Logs
                        </span>
                        {expandedLogs[act.action_name] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                    )}

                    {expandedLogs[act.action_name] && (
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl max-h-36 overflow-y-auto font-mono text-[9px] text-[#475569] space-y-2">
                        {history
                           .filter(h => h.action_name === act.action_name)
                           .map(h => (
                             <div key={h.id} className="border-b border-[#E2E8F0] pb-1.5 last:border-b-0 last:pb-0">
                               <div className="flex justify-between font-bold uppercase mb-1">
                                 <span>{new Date(h.timestamp).toLocaleTimeString()}</span>
                                 <span className={h.result === "SUCCESS" ? "text-[#16A34A]" : "text-[#DC2626]"}>{h.result}</span>
                               </div>
                               <pre className="whitespace-pre-wrap normal-case font-semibold">{h.logs}</pre>
                             </div>
                           ))}
                      </div>
                    )}

                    {!agentOnline ? (
                      <button
                        disabled={true}
                        className="w-full py-2 flex items-center justify-center gap-1.5 font-bold text-xs rounded-xl bg-red-50 border border-red-200 text-[#DC2626]"
                      >
                        <AlertCircle className="w-4 h-4" />
                        Device Agent Offline
                      </button>
                    ) : (
                      <button
                        onClick={() => setConfirmingAction(act)}
                        disabled={isExec || (!isApproved && user.role === "EMPLOYEE")}
                        className={`w-full py-2 flex items-center justify-center gap-1.5 font-bold text-xs rounded-xl cursor-pointer transition-all shadow-xs
                          ${isApproved 
                            ? "bg-[#E30613] hover:bg-red-700 text-white" 
                            : "bg-[#F1F5F9] border border-[#E2E8F0] text-[#94A3B8] disabled:opacity-40"}`}
                      >
                        {isExec ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Executing Task...
                          </>
                        ) : (
                          <>
                            <Play className="w-3.5 h-3.5" />
                            Execute Action
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Global execution audit logs table */}
        <div className="bg-white border border-[#E2E8F0] rounded-2xl shadow-xs overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-indigo-500" />
              <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">IT Automation Audit Logs</span>
            </div>
            <p className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">All actions executed across the Enterprise agent gateway.</p>
          </div>

          <div className="overflow-x-auto">
            {history.length === 0 ? (
              <div className="p-8 text-center text-[#94A3B8] italic font-semibold text-xs uppercase">No execution history recorded in the audits.</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Execution Time</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Device Host</TableHead>
                    <TableHead>Action Name</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Details Logs</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map(rec => (
                    <TableRow key={rec.id}>
                      <TableCell className="font-mono text-[#64748B] font-semibold">{new Date(rec.timestamp).toLocaleString()}</TableCell>
                      <TableCell className="text-[#0F172A] font-bold">{rec.username}</TableCell>
                      <TableCell className="font-mono text-[#64748B]">{rec.device_id}</TableCell>
                      <TableCell className="text-[#0F172A] font-bold">{rec.action_name}</TableCell>
                      <TableCell className="text-[#64748B] font-semibold">{rec.duration}s</TableCell>
                      <TableCell>
                        <StatusPill status={rec.result} />
                      </TableCell>
                      <TableCell className="text-right">
                        <button
                          onClick={() => setActiveExecResult(rec)}
                          className="text-[10px] font-bold text-indigo-500 hover:text-indigo-700 cursor-pointer uppercase tracking-wider"
                        >
                          View Logs
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmingAction && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl border border-[#E2E8F0] w-full max-w-md mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
              <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Confirm Execution</h3>
              <button onClick={() => setConfirmingAction(null)} className="text-[#94A3B8] hover:text-[#475569] cursor-pointer">
                ✕
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-4 rounded-xl space-y-2.5 text-xs font-bold">
                <div className="flex justify-between text-[#64748B] uppercase tracking-wider"><span>Target Host:</span><span className="text-[#1E293B]">{hostname}</span></div>
                <div className="flex justify-between text-[#64748B] uppercase tracking-wider"><span>Task Name:</span><span className="text-[#1E293B]">{confirmingAction.action_name}</span></div>
                <div className="flex justify-between text-[#64748B] uppercase tracking-wider">
                  <span>Approval Level:</span>
                  <span className="text-[#1E293B]">{confirmingAction.approval_required}</span>
                </div>
              </div>
              <p className="text-[11px] text-[#64748B] leading-normal font-semibold">
                This action executes dynamic commands on your corporate endpoint device. Verify that no critical unsaved work is in progress.
              </p>
            </div>
            <div className="flex gap-3 px-5 pb-5">
              <button
                onClick={() => setConfirmingAction(null)}
                className="flex-1 py-2 border border-[#E2E8F0] text-[#475569] text-xs font-bold rounded-xl hover:bg-[#F8FAFC] cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => handleExecute(confirmingAction)}
                className="flex-1 py-2 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-xl cursor-pointer"
              >
                Confirm &amp; Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Execution Logs Modal */}
      {activeExecResult && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl shadow-2xl border border-[#E2E8F0] w-full max-w-lg mx-4 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#E2E8F0] bg-[#F8FAFC]">
              <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-indigo-500" />
                Execution Log Output
              </h3>
              <button onClick={() => setActiveExecResult(null)} className="text-[#94A3B8] hover:text-[#475569] cursor-pointer">
                ✕
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs font-bold">
                <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl">
                  <span className="text-[9px] text-[#64748B] block uppercase tracking-wider">Action Name</span>
                  <span className="text-[#1E293B]">{activeExecResult.action_name}</span>
                </div>
                <div className="bg-[#F8FAFC] border border-[#E2E8F0] p-2.5 rounded-xl">
                  <span className="text-[9px] text-[#64748B] block uppercase tracking-wider">Duration</span>
                  <span className="text-[#1E293B]">{activeExecResult.duration} seconds</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-[9px] text-[#64748B] uppercase font-bold tracking-wider block">Console output logs</span>
                <pre className="p-3.5 bg-gray-950 text-gray-200 font-mono text-[10px] rounded-xl overflow-x-auto max-h-60 whitespace-pre-wrap leading-relaxed normal-case font-semibold">
                  {activeExecResult.logs}
                </pre>
              </div>
            </div>
            <div className="px-5 pb-5">
              <button
                onClick={() => setActiveExecResult(null)}
                className="w-full py-2 bg-[#475569] hover:bg-[#334155] text-white text-xs font-bold rounded-xl cursor-pointer"
              >
                Close Output
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
