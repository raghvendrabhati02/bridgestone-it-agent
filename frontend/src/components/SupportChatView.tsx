"use client";

import { useRef, useEffect, useMemo, useState } from "react";
import {
  Send, RefreshCw, Shield,
  Loader2, Brain, Search, Server,
  Wrench, FileText, CheckCircle2,
  Ticket, CheckCircle, XCircle,
  Mic, Paperclip, MessageSquare,
  AlertCircle, ChevronRight, ChevronLeft,
  Activity, BookOpen, Layers
} from "lucide-react";

import EnterpriseAdminAccessCard from "@/components/shared/EnterpriseAdminAccessCard";

// ─────────────────────────────────────────────────────────────
// Types
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

interface SupportChatViewProps {
  messages: Message[];
  message: string;
  setMessage: (m: string) => void;
  sendMessage: (text: string) => Promise<void>;
  startNewSession: () => void;
  sessionId: string | null;
  category: string;
  status: string;
  actions: string[];
  isLoading: boolean;
  error: string;
  approvalRequired: boolean;
  approvalStatus: string;
  recommendedAction: string;
  username: string;
}

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────
const SUGGESTION_CHIPS = [
  "VPN not connecting",
  "Outlook crashing",
  "Password expired",
  "Printer offline",
  "Teams not loading",
  "Wi-Fi issues",
  "Install SAP GUI",
];

// Investigation pipeline steps shown in the right panel.
const PIPELINE_STEPS = [
  { Icon: Brain, label: "Understanding Issue" },
  { Icon: Search, label: "Searching Knowledge Base" },
  { Icon: Wrench, label: "Running Troubleshooting" },
  { Icon: FileText, label: "Preparing Solution" },
];

function formatTime(d: Date): string {
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true });
}

function useInvestigationState(
  messages: Message[],
  isLoading: boolean,
  status: string,
  actions: string[],
) {
  return useMemo(() => {
    const agentMsgCount = messages.filter(m => m.sender === "agent").length;
    const lastAgent = messages.filter(m => m.sender === "agent").at(-1);
    const isResolved = status === "RESOLVED" || actions.includes("SOLVED");
    const isSolved = lastAgent?.action === "RESOLVED" || isResolved;
    const needsTicket = actions.length > 0 && !isSolved;
    const ticketCreated = lastAgent?.tool_result?.ticket_id
      || lastAgent?.tool_result?.id
      || null;

    let activeStep = -1;
    if (isLoading) {
      activeStep = Math.min(agentMsgCount, PIPELINE_STEPS.length - 1);
    }

    const completedUntil = isLoading
      ? activeStep - 1
      : agentMsgCount > 0 ? PIPELINE_STEPS.length - 1 : -1;

    const kbSource = messages
      .filter(m => m.sender === "agent" && m.source && m.context_used)
      .at(-1);

    return {
      activeStep,
      completedUntil,
      isSolved,
      needsTicket,
      ticketCreated,
      kbSource,
      agentMsgCount,
    };
  }, [messages, isLoading, status, actions]);
}

const ARTICLE_TOTAL_STEPS: Record<string, number> = {
  KB0001: 5,
  KB0002: 5,
  KB0003: 5,
  KB0004: 4,
  KB0005: 4,
  KB0006: 5,
  KB0007: 5,
  KB0008: 5,
  KB0009: 5,
  KB0010: 5,
};

function parseTroubleshootingText(text: string) {
  const stepMatch = text.match(/Step\s+(\d+):\s*(.+)/i);
  const stepNumber = stepMatch ? parseInt(stepMatch[1], 10) : 1;
  const title = stepMatch ? stepMatch[2].trim() : "";

  let cleanText = text.replace(/Step\s+(\d+):\s*(.+)/i, "").trim();

  const screenshotMatch = cleanText.match(/\[Screenshot:\s*([^\s\]]+)(?:\s*[-—]\s*([^\]]+))?\]/i);
  let image = "";
  let caption = "";
  if (screenshotMatch) {
    image = screenshotMatch[1].trim();
    if (screenshotMatch[2]) {
      caption = screenshotMatch[2].trim();
    }
    cleanText = cleanText.replace(/\[Screenshot:\s*([^\s\]]+)(?:\s*[-—]\s*([^\]]+))?\]/i, "").trim();
  }

  // Remove leftover raw filenames (e.g. vpn_step1.png)
  cleanText = cleanText.replace(/[\w-]+\.(?:png|jpg)/gi, "").trim();

  cleanText = cleanText.replace(/Have you completed this step\??/i, "")
    .replace(/Did that work\??/i, "")
    .trim();

  return {
    stepNumber,
    title,
    instruction: cleanText,
    image,
    caption
  };
}

function SafeImage({ image, caption, setZoomImage }: { image: string; caption?: string; setZoomImage: (img: string | null) => void }) {
  const [imgError, setImgError] = useState(false);

  if (imgError || !image) return null;

  return (
    <div className="border border-[#E2E8F0] rounded-xl p-1 bg-[#F8FAFC] overflow-hidden group max-w-sm">
      <div
        className="relative aspect-video bg-[#E2E8F0] rounded-lg overflow-hidden cursor-zoom-in"
        onClick={() => setZoomImage(image)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`/images/${image}`}
          alt={caption || "Screenshot"}
          className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
          onError={() => {
            setImgError(true);
          }}
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors" />
      </div>
      {caption && (
        <p className="text-[10px] text-[#64748B] italic text-center mt-1.5 font-bold px-2 uppercase tracking-wider">
          {caption}
        </p>
      )}
    </div>
  );
}

function MessageBubble({ text, isUser, username, setZoomImage }: { text: string; isUser: boolean; username: string; setZoomImage: (img: string | null) => void }) {
  if (isUser) {
    return (
      <div className="px-4 py-2.5 rounded-2xl text-xs leading-relaxed font-semibold bg-[#E30613] text-white rounded-br-sm shadow-sm">
        <span className="whitespace-pre-wrap">{text}</span>
      </div>
    );
  }

  const screenshotMatch = text.match(/\[Screenshot:\s*([^\s\]]+)(?:\s*[-—]\s*([^\]]+))?\]/i);
  let cleanText = text;
  let image = "";
  let caption = "";

  if (screenshotMatch) {
    image = screenshotMatch[1].trim();
    if (screenshotMatch[2]) {
      caption = screenshotMatch[2].trim();
    }
    cleanText = text.replace(/\[Screenshot:\s*([^\s\]]+)(?:\s*[-—]\s*([^\]]+))?\]/i, "").trim();
  }

  // Remove leftover raw filenames (e.g. vpn_step1.png)
  cleanText = cleanText.replace(/[\w-]+\.(?:png|jpg)/gi, "").trim();

  return (
    <div className="space-y-2">
      {cleanText && (
        <div className="px-4 py-2.5 rounded-2xl text-xs leading-relaxed font-semibold bg-[#F8FAFC] border border-[#E2E8F0] text-[#1E293B] rounded-bl-sm">
          <span className="whitespace-pre-wrap">{cleanText}</span>
        </div>
      )}
      {image && (
        <SafeImage image={image} caption={caption} setZoomImage={setZoomImage} />
      )}
    </div>
  );
}

export default function SupportChatView({
  messages,
  message,
  setMessage,
  sendMessage,
  startNewSession,
  sessionId,
  isLoading,
  error,
  actions,
  approvalRequired,
  approvalStatus,
  recommendedAction,
  username,
  status,
  category,
}: SupportChatViewProps) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [zoomImage, setZoomImage] = useState<string | null>(null);
  const [isInvestigationOpen, setIsInvestigationOpen] = useState(false);

  const inv = useInvestigationState(messages, isLoading, status, actions);

  // Auto-expand investigation panel on desktop when conversation starts
  useEffect(() => {
    if (messages.length > 0 || isLoading) {
      setIsInvestigationOpen(true);
    }
  }, [messages.length, isLoading]);

  const focusInput = () => {
    requestAnimationFrame(() => {
      const textarea = inputRef.current;
      if (textarea) {
        textarea.focus();
        const len = textarea.value.length;
        textarea.setSelectionRange(len, len);
      }
    });
  };

  const adjustHeight = () => {
    const textarea = inputRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      const scrollHeight = textarea.scrollHeight;
      const maxHeight = 120; // 6 lines cap (approx 20px per line)
      textarea.style.height = `${Math.min(scrollHeight, maxHeight)}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [message]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading, actions.length, error, approvalStatus]);

  useEffect(() => {
    if (!isLoading) {
      focusInput();
    }
  }, [messages.length, isLoading, approvalStatus, error, actions]);

  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        startNewSession();
      }
      if (e.ctrlKey && e.key === "/") {
        e.preventDefault();
        focusInput();
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [startNewSession]);

  const msgTimes = useMemo(
    () => messages.map(() => formatTime(new Date())),
    [messages.length],
  );

  const showInput =
    actions.length === 0 && (!approvalRequired || approvalStatus !== "PENDING");

  const inputIsDisabled = isLoading;

  const lastToolResult = messages
    .filter(m => m.sender === "agent" && m.tool_result)
    .at(-1)?.tool_result;

  const renderInvestigationStatus = () => {
    const lastAgentMsg = messages.filter(m => m.sender === "agent").at(-1);
    const tbState = lastAgentMsg?.tool_result?.["_tb_engine_state"];
    const hasStarted = messages.length > 0 || isLoading;
    const isSolved = inv.isSolved || status === "RESOLVED";
    const isTicketCreated = Boolean(lastToolResult?.ticket_id);
    const isEscalated = status === "ESCALATED" || isTicketCreated;

    // Current Phase Title
    let phaseTitle = "Idle / Ready";
    let phaseSubtitle = "Awaiting user inquiry";
    let phaseBadgeCls = "bg-[#F1F5F9] text-[#64748B] border-[#CBD5E1]";

    if (isSolved) {
      phaseTitle = "Issue Resolved";
      phaseSubtitle = "Resolution confirmed";
      phaseBadgeCls = "bg-emerald-50 text-emerald-700 border-emerald-200";
    } else if (isEscalated) {
      phaseTitle = "ServiceNow Escalation";
      phaseSubtitle = "Ticket created in ITSM queue";
      phaseBadgeCls = "bg-amber-50 text-amber-700 border-amber-200";
    } else if (tbState?.is_troubleshooting || inv.activeStep >= 2) {
      phaseTitle = "AI Troubleshooting";
      phaseSubtitle = "Executing step-by-step resolution";
      phaseBadgeCls = "bg-blue-50 text-blue-700 border-blue-200";
    } else if (isLoading) {
      phaseTitle = "Diagnosing Issue";
      phaseSubtitle = "Analyzing intent & searching SOPs";
      phaseBadgeCls = "bg-purple-50 text-purple-700 border-purple-200";
    } else if (hasStarted) {
      phaseTitle = "Active Investigation";
      phaseSubtitle = "Evaluating user request";
      phaseBadgeCls = "bg-indigo-50 text-indigo-700 border-indigo-200";
    }

    const rawCategory = category || lastAgentMsg?.category || messages.find(m => m.category)?.category || "General IT";
    const formattedCategory = rawCategory.toUpperCase().replace("_", " ");

    const articleId = tbState?.troubleshooting_session?.article_id
      || (inv.kbSource?.source ?? (hasStarted ? "KB0001" : null));
    const articleTitle = inv.kbSource?.source || (articleId ? `SOP Guide (${articleId})` : "General Support Document");

    const totalSteps = ARTICLE_TOTAL_STEPS[articleId ?? "KB0001"] ?? 5;
    const stepDetails = parseTroubleshootingText(lastAgentMsg?.text || "");
    const currentStepNum = stepDetails.stepNumber || (inv.activeStep >= 0 ? inv.activeStep + 1 : 1);

    // Build Stage list dynamically: includes Escalation stage when escalated or ticket created
    const activeStages = [
      ...PIPELINE_STEPS.map((s, idx) => ({
        key: idx === 0 ? "understanding" : idx === 1 ? "knowledge_base" : idx === 2 ? "troubleshooting" : "solution",
        label: s.label,
        Icon: s.Icon,
      })),
      ...(isEscalated ? [{ key: "escalation", label: "Escalated to ServiceNow", Icon: Ticket }] : [])
    ];

    // Helper to compute state per stage (completed | current | pending)
    const getStageStatus = (stageKey: string): "completed" | "current" | "pending" => {
      if (isSolved) {
        if (stageKey === "escalation") return "pending";
        return "completed";
      }

      if (isTicketCreated || isEscalated) {
        return "completed";
      }

      if (isLoading) {
        if (inv.agentMsgCount === 0) {
          return stageKey === "understanding" ? "current" : "pending";
        }
        if (inv.agentMsgCount === 1) {
          if (stageKey === "understanding") return "completed";
          if (stageKey === "knowledge_base") return "current";
          return "pending";
        }
        if (tbState?.is_troubleshooting) {
          if (["understanding", "knowledge_base"].includes(stageKey)) return "completed";
          if (stageKey === "troubleshooting") return "current";
          return "pending";
        }
        if (["understanding", "knowledge_base", "troubleshooting"].includes(stageKey)) return "completed";
        if (stageKey === "solution") return "current";
        return "pending";
      }

      if (tbState?.is_troubleshooting) {
        if (["understanding", "knowledge_base"].includes(stageKey)) return "completed";
        if (stageKey === "troubleshooting") return "current";
        return "pending";
      }

      if (inv.agentMsgCount > 0) {
        if (["understanding", "knowledge_base", "troubleshooting"].includes(stageKey)) return "completed";
        if (stageKey === "solution") return "current";
        return "pending";
      }

      return "pending";
    };

    return (
      <div className="flex flex-col h-full bg-[#F8FAFC]">
        {/* Panel Header */}
        <div className="flex-shrink-0 px-4 py-3 border-b border-[#E2E8F0] bg-white flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-[#E30613]" />
            </div>
            <div>
              <h3 className="text-xs font-black text-[#0F172A] uppercase tracking-wider">
                Investigation Workflow
              </h3>
              <p className="text-[9px] text-[#64748B] font-semibold uppercase tracking-wider">
                ITSM Status Tracking
              </p>
            </div>
          </div>

          <button
            onClick={() => setIsInvestigationOpen(false)}
            className="p-1.5 rounded-lg text-[#64748B] hover:text-[#1E293B] hover:bg-[#F1F5F9] transition-colors cursor-pointer"
            aria-label="Collapse Investigation Panel"
            title="Collapse Panel"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Panel Body */}
        <div className="flex-1 px-4 py-4 space-y-4 overflow-y-auto">
          {!hasStarted ? (
            /* Initial Placeholder / Waiting State */
            <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 text-center space-y-3 shadow-2xs">
              <div className="w-12 h-12 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-center mx-auto text-[#94A3B8]">
                <Brain className="w-6 h-6 text-[#94A3B8]" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Ready for Investigation</h4>
                <p className="text-[11px] text-[#64748B] font-medium leading-relaxed mt-1">
                  Describe your issue in the chat to start live diagnostics, knowledge retrieval, and step-by-step troubleshooting.
                </p>
              </div>
              <button
                onClick={() => focusInput()}
                className="w-full py-2 bg-[#F8FAFC] hover:bg-[#F1F5F9] border border-[#E2E8F0] text-xs font-bold text-[#E30613] rounded-lg transition-colors cursor-pointer uppercase tracking-wider"
              >
                Describe An Issue
              </button>
            </div>
          ) : (
            <>
              {/* 1. CURRENT PHASE & CATEGORY */}
              <div className="bg-white border border-[#E2E8F0] rounded-xl p-3.5 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Current Phase</span>
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${phaseBadgeCls}`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                    {phaseTitle}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#F1F5F9]">
                  <div>
                    <span className="text-[9px] font-bold text-[#94A3B8] uppercase tracking-wider block">Category</span>
                    <span className="text-xs font-bold text-[#0F172A] truncate block mt-0.5">{formattedCategory}</span>
                  </div>
                  <div>
                    <span className="text-[9px] font-bold text-[#94A3B8] uppercase tracking-wider block">Sub-Status</span>
                    <span className="text-xs font-semibold text-[#475569] truncate block mt-0.5">{phaseSubtitle}</span>
                  </div>
                </div>
              </div>

              {/* 2. WORKFLOW STAGES (STATUS-BASED NO PERCENTAGES) */}
              <div className="bg-white border border-[#E2E8F0] rounded-xl p-3.5 space-y-3 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Workflow Stages</span>
                  <span className="text-[9px] font-bold text-[#64748B] uppercase tracking-wider bg-[#F8FAFC] border border-[#E2E8F0] px-2 py-0.5 rounded">
                    Status-Driven
                  </span>
                </div>

                {/* Active Step callout when troubleshooting */}
                {tbState?.is_troubleshooting && stepDetails.title && !isSolved && !isTicketCreated && (
                  <div className="bg-[#FEF2F2] border border-[#FEE2E2] rounded-lg p-2.5 space-y-1">
                    <span className="text-[9px] font-bold text-[#E30613] uppercase tracking-wider block">
                      Active Step {currentStepNum} of {totalSteps}
                    </span>
                    <p className="text-xs font-bold text-[#0F172A] leading-snug">{stepDetails.title}</p>
                  </div>
                )}

                {/* Workflow Stages List */}
                <div className="space-y-1.5 pt-1">
                  {activeStages.map((stage) => {
                    const statusType = getStageStatus(stage.key);
                    const isCompleted = statusType === "completed";
                    const isCurrent = statusType === "current";

                    return (
                      <div
                        key={stage.key}
                        className={`flex items-center justify-between px-3 py-2 rounded-xl border text-xs transition-all ${
                          isCurrent
                            ? "bg-blue-50/90 border-blue-200 shadow-2xs font-bold text-blue-950"
                            : isCompleted
                            ? "bg-white border-[#E2E8F0] font-semibold text-[#1E293B]"
                            : "bg-transparent border-transparent text-[#94A3B8] font-normal"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`w-5 h-5 rounded-lg flex items-center justify-center flex-shrink-0 ${
                            isCompleted
                              ? "bg-emerald-50 border border-emerald-200 text-emerald-600"
                              : isCurrent
                              ? "bg-blue-600 text-white shadow-2xs"
                              : "bg-[#F1F5F9] text-[#CBD5E1]"
                          }`}>
                            {isCompleted ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            ) : isCurrent ? (
                              <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                            ) : (
                              <stage.Icon className="w-3 h-3 text-[#94A3B8]" />
                            )}
                          </div>
                          <span className="truncate text-xs tracking-tight">{stage.label}</span>
                        </div>

                        <div>
                          {isCompleted ? (
                            <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-600 uppercase tracking-wider">
                              Done
                            </span>
                          ) : isCurrent ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-bold bg-blue-100 text-blue-700 uppercase tracking-wider">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
                              Active
                            </span>
                          ) : (
                            <span className="text-[9px] font-semibold text-[#CBD5E1] uppercase tracking-wider">
                              Pending
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 3. KNOWLEDGE BASE CITATION (NO PERCENTAGE) */}
              {articleId && (
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-3.5 space-y-2 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider flex items-center gap-1.5">
                      <BookOpen className="w-3 h-3 text-[#E30613]" />
                      Knowledge Base Citation
                    </span>
                    <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded uppercase tracking-wider">
                      SOP Verified
                    </span>
                  </div>
                  <p className="text-xs font-bold text-[#0F172A] leading-snug">
                    {articleTitle}
                  </p>
                  <div className="flex items-center justify-between pt-1.5 border-t border-[#F1F5F9] text-[10px] text-[#64748B] font-semibold">
                    <span>Article ID</span>
                    <span className="text-[#1E293B] font-mono font-bold">{articleId}</span>
                  </div>
                </div>
              )}

              {/* 4. RESOLVED OR SERVICENOW TICKET CARD */}
              {isSolved && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-2 shadow-2xs">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <h4 className="text-xs font-bold text-emerald-900 uppercase tracking-wider">Issue Solved</h4>
                  </div>
                  <p className="text-xs text-emerald-800 leading-relaxed font-medium">
                    The AI successfully resolved your issue. No ServiceNow escalation was required.
                  </p>
                </div>
              )}

              {lastToolResult?.ticket_id && (
                <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 space-y-3 shadow-2xs">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Ticket className="w-4 h-4 text-[#E30613]" />
                      <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">ServiceNow Ticket</h4>
                    </div>
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 uppercase tracking-wider">
                      Created
                    </span>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-[#F1F5F9]">
                    {[
                      { label: "Ticket Number", value: lastToolResult.ticket_id as string, isMono: true },
                      { label: "Assigned Team", value: (lastToolResult.assigned_team as string) ?? "IT Support" },
                      { label: "Priority", value: (lastToolResult.priority as string) ?? "Medium" },
                      { label: "Target SLA", value: `${lastToolResult.sla_hours ?? 4} Hours` },
                    ].map(({ label, value, isMono }) => (
                      <div key={label} className="flex justify-between items-center text-xs">
                        <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">{label}</span>
                        <span className={`font-bold ${isMono ? "text-[#E30613] font-mono text-xs" : "text-[#1E293B]"}`}>
                          {value}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Phase 6.3: Approval Pending Panel — shown when manager approval is required */}
                  {(lastToolResult.requires_approval || lastToolResult.ticket_status === "WAITING_MANAGER") && lastToolResult.ticket_status !== "ACCESS_GRANTED" && status !== "ACCESS_GRANTED" && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5 space-y-3 mt-2">
                      <div className="flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                        <span className="text-xs font-bold text-amber-900 uppercase tracking-wider">Manager Approval Required</span>
                        <span className="ml-auto w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                      </div>
                      <p className="text-[11px] text-amber-800 leading-relaxed font-semibold">
                        Your request has been submitted for manager approval.
                        Once approved, IT administration will grant temporary access to proceed.
                      </p>
                      {/* Workflow mini-progress */}
                      <div className="space-y-1.5 pt-1 border-t border-amber-200">
                        {[
                          { label: "Request Submitted", done: true },
                          { label: "Awaiting Manager", done: false, active: true },
                          { label: "Admin Access Grant", done: false },
                          { label: "Installation", done: false },
                        ].map((step, i) => (
                          <div key={i} className="flex items-center gap-2">
                            <div className={`w-3.5 h-3.5 rounded-full flex-shrink-0 flex items-center justify-center ${
                              step.done ? "bg-emerald-500" : step.active ? "bg-amber-400 animate-pulse" : "bg-amber-100 border border-amber-300"
                            }`}>
                              {step.done && (
                                <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                </svg>
                              )}
                            </div>
                            <span className={`text-[10px] font-bold ${
                              step.done ? "text-emerald-700 line-through" : step.active ? "text-amber-800" : "text-amber-400"
                            }`}>{step.label}</span>
                            {step.active && (
                              <span className="text-[9px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ml-auto">Pending</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Phase 6.3: Temporary Admin Credentials Card — shown when ACCESS_GRANTED */}
                  {(status === "ACCESS_GRANTED" || lastToolResult?.ticket_status === "ACCESS_GRANTED" || lastToolResult?.laps_active || lastToolResult?.temp_admin_credentials) && (
                    <div className="mt-3">
                      <EnterpriseAdminAccessCard
                        username={lastToolResult?.temp_admin_credentials?.username || ".\\Administrator"}
                        password={lastToolResult?.temp_admin_credentials?.password || "Temp@4821#"}
                        expiresAt={lastToolResult?.temp_admin_credentials?.expires_at}
                      />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#F8FAFC] overflow-hidden font-sans">

      {/* Top Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-b border-[#E2E8F0] bg-white">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center">
            <MessageSquare className="w-3.5 h-3.5 text-[#E30613]" />
          </div>
          <div>
            <h2 className="text-xs font-black text-[#0F172A] leading-none uppercase tracking-wider">IT Support Assistant</h2>
            <p className="text-[10px] text-[#64748B] font-semibold mt-0.5 uppercase tracking-wider">
              AI-powered diagnosis &amp; issue resolution
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Chevron Panel Toggle Button */}
          <button
            onClick={() => setIsInvestigationOpen(!isInvestigationOpen)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] hover:border-[#CBD5E1] text-xs font-bold text-[#334155] rounded-xl transition-all cursor-pointer shadow-2xs"
            title={isInvestigationOpen ? "Collapse Investigation Panel" : "Expand Investigation Panel"}
            aria-label={isInvestigationOpen ? "Collapse Investigation Panel" : "Expand Investigation Panel"}
          >
            <Brain className="w-3.5 h-3.5 text-[#E30613]" />
            <span className="hidden sm:inline">Investigation</span>
            <ChevronRight className={`w-3.5 h-3.5 transition-transform duration-200 ${isInvestigationOpen ? "rotate-180" : ""}`} />
          </button>

          {sessionId && (
            <button
              onClick={startNewSession}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl transition-all cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              <span className="hidden sm:inline">New Session</span>
            </button>
          )}
        </div>
      </div>

      {/* Three-Column Body (Left Chat flex-1, Right Investigation Panel w-[340px] inline) */}
      <div className="flex-1 min-h-0 flex overflow-hidden relative">

        {/* LEFT COLUMN — CHAT AREA (flex-1 min-w-0, resizes automatically) */}
        <div className="flex-1 min-w-0 flex flex-col bg-white">
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

            {/* Welcome message */}
            {messages.length === 0 && !isLoading && (
              <div className="h-full flex flex-col items-center justify-center text-center gap-5 py-8">
                <div className="w-14 h-14 rounded-2xl bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center">
                  <Brain className="w-7 h-7 text-[#E30613]" />
                </div>

                <div>
                  <h3 className="text-sm font-black text-[#0F172A] uppercase tracking-wider">
                    Enterprise IT Support Assistant
                  </h3>
                  <p className="text-xs text-[#475569] font-medium mt-1.5 max-w-sm leading-relaxed">
                    Describe your issue in plain English. I'll diagnose it, check our knowledge base,
                    and resolve it — or create a ServiceNow ticket if needed.
                  </p>
                </div>

                {/* Example box */}
                <div className="text-left bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 w-full max-w-sm">
                  <p className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider mb-2.5">Examples</p>
                  <ul className="space-y-1.5 font-semibold">
                    {["VPN is not connecting", "Outlook keeps crashing", "My password expired", "My printer is offline"].map(ex => (
                      <li key={ex} className="flex items-center gap-2 text-xs text-[#475569]">
                        <span className="w-1 h-1 rounded-full bg-[#E30613] inline-block flex-shrink-0" />
                        {ex}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Chips */}
                <div className="flex flex-wrap gap-2 justify-center max-w-sm">
                  {SUGGESTION_CHIPS.map(chip => (
                    <button
                      key={chip}
                      onClick={() => sendMessage(chip)}
                      className="px-3 py-1.5 bg-white border border-[#E2E8F0] hover:border-[#E30613] hover:text-[#E30613] hover:bg-[#FEF2F2]/50 rounded-full text-xs font-bold text-[#475569] transition-all cursor-pointer shadow-xs"
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Conversation turns */}
            {useMemo(() => {
              return messages.map((msg, idx) => {
                const isUser = msg.sender === "user";
                return (
                  <div
                    key={idx}
                    className={`flex items-end gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    {!isUser && (
                      <div className="w-6 h-6 rounded-full bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center flex-shrink-0 mb-0.5">
                        <Brain className="w-3 h-3 text-[#E30613]" />
                      </div>
                    )}

                    <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
                      <div className={`flex items-center gap-1.5 ${isUser ? "flex-row-reverse" : ""}`}>
                        <span className="text-[10px] font-bold text-[#64748B]">
                          {isUser ? username : "IT Support AI"}
                        </span>
                        <span className="text-[9px] text-[#94A3B8] font-medium">{msgTimes[idx]}</span>
                      </div>

                      {isUser || !msg.type || msg.type === "plain" ? (
                        <MessageBubble
                          text={msg.text}
                          isUser={isUser}
                          username={username}
                          setZoomImage={setZoomImage}
                        />
                      ) : msg.type === "troubleshooting" ? (
                        (() => {
                          const details = parseTroubleshootingText(msg.text);
                          const totalSteps = ARTICLE_TOTAL_STEPS[msg.tool_result?.["_tb_engine_state"]?.["troubleshooting_session"]?.["article_id"] ?? "KB0001"] ?? 5;
                          return (
                            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4 max-w-md w-full text-left">
                              <div className="flex items-center justify-between text-[10px] font-bold text-[#64748B] border-b border-[#F1F5F9] pb-2">
                                <span className="uppercase text-[#E30613] tracking-wider">Troubleshooting Step {details.stepNumber}</span>
                                <span className="uppercase tracking-wider">Step {details.stepNumber} of {totalSteps}</span>
                              </div>
                              <div>
                                <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">{details.title}</h3>
                                <p className="text-xs text-[#334155] mt-1.5 leading-relaxed font-medium">{details.instruction}</p>
                              </div>
                              {details.image && (
                                <SafeImage
                                  image={details.image}
                                  caption={details.caption}
                                  setZoomImage={setZoomImage}
                                />
                              )}
                              <div className="pt-2 border-t border-[#E2E8F0] flex items-center justify-between gap-3">
                                <span className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">Did this resolve your issue?</span>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => sendMessage("Yes, that solved my issue.")}
                                    className="px-3 py-1 bg-green-50 text-green-700 border border-green-200 rounded-lg text-xs font-bold hover:bg-green-100 transition-colors cursor-pointer"
                                  >
                                    Yes
                                  </button>
                                  <button
                                    onClick={() => sendMessage("No, that did not work.")}
                                    className="px-3 py-1 bg-red-50 text-[#E30613] border border-red-200 rounded-lg text-xs font-bold hover:bg-red-100 transition-colors cursor-pointer"
                                  >
                                    No
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })()
                      ) : msg.type === "verification" ? (
                        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-3 max-w-md w-full text-left">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Confirm Resolution</h4>
                          </div>
                          <p className="text-xs text-[#334155] font-medium leading-relaxed">{msg.text}</p>
                          <div className="pt-2 border-t border-[#E2E8F0] flex gap-2">
                            <button
                              onClick={() => sendMessage("Yes, my issue is resolved.")}
                              className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shadow-2xs"
                            >
                              Yes, Resolved
                            </button>
                            <button
                              onClick={() => sendMessage("No, I still need help.")}
                              className="px-3.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                            >
                              No, Still Broken
                            </button>
                          </div>
                        </div>
                      ) : msg.type === "ticket_confirmation" ? (
                        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-3 max-w-md w-full text-left">
                          <div className="flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 text-amber-500" />
                            <h4 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">ServiceNow Ticket Creation</h4>
                          </div>
                          <p className="text-xs text-[#334155] font-medium leading-relaxed">{msg.text}</p>
                          <div className="pt-2 border-t border-[#E2E8F0] flex gap-2">
                            <button
                              onClick={() => sendMessage("Yes, please create a ticket.")}
                              className="px-3.5 py-1.5 bg-[#E30613] hover:bg-red-700 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shadow-2xs"
                            >
                              Create Ticket
                            </button>
                            <button
                              onClick={() => sendMessage("No, don't create a ticket yet.")}
                              className="px-3.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9] rounded-lg text-xs font-bold transition-colors cursor-pointer"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <MessageBubble
                          text={msg.text}
                          isUser={isUser}
                          username={username}
                          setZoomImage={setZoomImage}
                        />
                      )}
                    </div>
                  </div>
                );
              });
            }, [messages, username, msgTimes, setZoomImage, sendMessage])}

            {isLoading && (
              <div className="flex items-center gap-2 text-xs text-[#64748B] font-semibold py-2">
                <div className="w-6 h-6 rounded-full bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center flex-shrink-0">
                  <Brain className="w-3 h-3 text-[#E30613]" />
                </div>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#E30613]" />
                <span>AI Agent is analyzing request...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          {showInput && (
            <div className="p-4 border-t border-[#E2E8F0] bg-white">
              <div className="flex items-end gap-2 bg-[#F8FAFC] border border-[#E2E8F0] focus-within:border-[#E30613] focus-within:ring-1 focus-within:ring-[#E30613]/20 rounded-2xl p-2 transition-all shadow-2xs">
                
                {/* TODO: Enable screenshot and file upload support.
                    Planned support:
                    - PNG
                    - JPG
                    - PDF
                    - DOCX
                    - Log files
                    - Drag & Drop
                    - Clipboard image paste */}
                <button
                  type="button"
                  disabled
                  title="📎 Attach Screenshot or File (Coming Soon)"
                  aria-label="Attach Screenshot or File (Coming Soon)"
                  className="p-1.5 rounded-lg text-[#94A3B8] hover:text-[#64748B] opacity-60 cursor-not-allowed transition-opacity flex-shrink-0 mb-0.5"
                >
                  <Paperclip className="w-4 h-4" />
                </button>

                <textarea
                  ref={inputRef}
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Escape") {
                      e.preventDefault();
                      setMessage("");
                    }
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      if (message.trim() && !inputIsDisabled) {
                        sendMessage(message);
                      }
                    }
                  }}
                  disabled={inputIsDisabled}
                  placeholder="Describe your IT issue..."
                  rows={1}
                  className="flex-1 bg-transparent text-xs text-[#1E293B] font-semibold placeholder-gray-400 focus:outline-none min-w-0 resize-none py-1.5 leading-normal max-h-[120px] overflow-y-auto"
                  aria-label="IT issue description"
                />

                <button
                  className="p-1 rounded text-gray-300 hover:text-gray-400 transition-colors cursor-not-allowed"
                  title="Voice input (coming soon)"
                  disabled
                  type="button"
                >
                  <Mic className="w-4 h-4" />
                </button>

                <button
                  onClick={() => { if (message.trim() && !inputIsDisabled) sendMessage(message); }}
                  disabled={inputIsDisabled || !message.trim()}
                  className="flex items-center justify-center w-7 h-7 rounded-lg bg-[#E30613] hover:bg-red-700 disabled:bg-[#E2E8F0] text-white transition-colors cursor-pointer flex-shrink-0 shadow-2xs"
                  aria-label="Send Message"
                  type="button"
                >
                  {isLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
              <p className="text-[10px] text-[#94A3B8] font-bold uppercase tracking-wider mt-1.5 text-center">
                IT Support AI · Powered by Enterprise AI · Bridgestone Enterprise
              </p>
            </div>
          )}
        </div>

        {/* MOBILE DRAWER OVERLAY BACKDROP & DRAWER (< md) */}
        {isInvestigationOpen && (
          <div
            onClick={() => setIsInvestigationOpen(false)}
            className="md:hidden fixed inset-0 bg-slate-900/40 backdrop-blur-2xs z-40 transition-opacity duration-200"
          />
        )}
        <aside
          className={`fixed inset-y-0 right-0 z-50 w-80 max-w-[85vw] bg-white border-l border-[#E2E8F0] flex flex-col shadow-2xl transform transition-transform duration-300 ease-in-out md:hidden ${
            isInvestigationOpen ? "translate-x-0" : "translate-x-full"
          }`}
        >
          {renderInvestigationStatus()}
        </aside>

        {/* RIGHT COLUMN — INVESTIGATION STATUS PANEL (DESKTOP & TABLET INLINE THREE-COLUMN) */}
        <aside
          className={`hidden md:flex flex-col bg-[#F8FAFC] border-l border-[#E2E8F0] flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden ${
            isInvestigationOpen ? "w-[340px] opacity-100" : "w-0 opacity-0 border-l-0"
          }`}
        >
          <div className="w-[340px] h-full flex flex-col flex-shrink-0">
            {renderInvestigationStatus()}
          </div>
        </aside>

      </div>

      {zoomImage && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-2xs z-50 flex items-center justify-center p-4 cursor-zoom-out"
          onClick={() => setZoomImage(null)}
        >
          <div className="relative max-w-4xl max-h-[85vh] bg-white p-2 rounded-xl shadow-2xl overflow-hidden" onClick={e => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`/images/${zoomImage}`}
              alt="Zoomed screenshot"
              className="max-w-full max-h-[80vh] object-contain rounded-lg"
              onError={(e) => {
                (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1531403009284-440f080d1e12?w=800&auto=format&fit=crop&q=60";
              }}
            />
            <p className="text-center text-[10px] font-bold text-[#64748B] mt-2 uppercase tracking-wider">
              Click background to close
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
