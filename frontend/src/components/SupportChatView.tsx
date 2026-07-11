"use client";

import { useRef, useEffect, useMemo, useState } from "react";
import {
  Send, RefreshCw, Shield,
  Loader2, Brain, Search, Server,
  Wrench, FileText, CheckCircle2,
  Ticket, CheckCircle, XCircle,
  Mic, Paperclip, MessageSquare,
  AlertCircle
} from "lucide-react";

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
  { Icon: Server, label: "Checking Device Information" },
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
}: SupportChatViewProps) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [zoomImage, setZoomImage] = useState<string | null>(null);
  const [isInvestigationOpen, setIsInvestigationOpen] = useState(false);

  const inv = useInvestigationState(messages, isLoading, status, actions);

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
    return (
      <div className="flex flex-col h-full bg-[#F8FAFC]">
        <div className="flex-shrink-0 px-4 py-3 border-b border-[#E2E8F0] bg-white flex items-center justify-between">
          <p className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
            Investigation Status
          </p>
          <button
            onClick={() => setIsInvestigationOpen(false)}
            className="lg:hidden p-1 rounded-lg text-[#64748B] hover:bg-[#F1F5F9] cursor-pointer"
            aria-label="Close status drawer"
          >
            <XCircle className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 px-4 py-4 space-y-4 overflow-y-auto">
          {messages.length === 0 && !isLoading && (
            <div className="text-center py-6">
              <div className="w-10 h-10 rounded-full bg-white border border-[#E2E8F0] flex items-center justify-center mx-auto mb-3">
                <Brain className="w-5 h-5 text-[#94A3B8]" />
              </div>
              <p className="text-[10.5px] text-[#64748B] font-bold leading-relaxed uppercase">
                Investigation steps will appear here once you describe your issue.
              </p>
            </div>
          )}

          {(messages.length > 0 || isLoading) && (
            <div className="space-y-2">
              {PIPELINE_STEPS.map((step, idx) => {
                const isDone = idx <= inv.completedUntil;
                const isActive = idx === inv.activeStep && isLoading;

                return (
                  <div
                    key={step.label}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg border transition-all ${isActive
                      ? "bg-white border-[#E30613]/20 shadow-xs"
                      : isDone
                        ? "bg-white border-green-155"
                        : "border-transparent"
                      }`}
                  >
                    <div className={`w-5 h-5 rounded flex items-center justify-center flex-shrink-0 ${isDone ? "bg-green-50" : isActive ? "bg-[#FEF2F2]" : "bg-[#F1F5F9]"
                      }`}>
                      {isDone ? (
                        <CheckCircle2 className="w-3 h-3 text-[#16A34A]" />
                      ) : isActive ? (
                        <Loader2 className="w-3 h-3 text-[#E30613] animate-spin" />
                      ) : (
                        <step.Icon className="w-3 h-3 text-[#94A3B8]" />
                      )}
                    </div>

                    <span className={`text-xs font-semibold leading-none ${isDone ? "text-green-700" : isActive ? "text-[#1E293B]" : "text-[#94A3B8]"
                      }`}>
                      {step.label}
                    </span>
                  </div>
                );
              })}

              {!isLoading && messages.length > 0 && !inv.isSolved && actions.length === 0 && (
                <p className="text-[9px] text-[#64748B] font-bold uppercase px-3 pt-1 italic tracking-wider">
                  Waiting for your response...
                </p>
              )}
            </div>
          )}

          {inv.kbSource && (
            <div className="bg-white border border-[#E2E8F0] rounded-lg p-3 space-y-2 shadow-xs">
              <p className="text-[10px] font-bold text-[#64748B] uppercase tracking-wider">
                Knowledge Base
              </p>
              <div className="flex items-start gap-2">
                <Search className="w-3.5 h-3.5 text-[#E30613] flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-bold text-[#1E293B]">
                    {inv.kbSource.source ?? "SOP Document"}
                  </p>
                  <p className="text-[10px] text-[#64748B] font-bold mt-0.5 uppercase">
                    {inv.kbSource.category ?? "Troubleshooting Guide"}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-[#E2E8F0]">
                <span className="text-[10px] text-[#64748B] font-bold uppercase">Confidence</span>
                <span className="text-[10px] font-bold text-[#16A34A]">94%</span>
              </div>
            </div>
          )}

          {inv.isSolved && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-[#16A34A] flex-shrink-0" />
                <p className="text-xs font-bold text-green-800 uppercase tracking-wider">Issue Resolved</p>
              </div>
              <p className="text-[11px] text-green-700 leading-relaxed font-bold">
                The AI resolved your issue successfully. No ticket was created.
              </p>
            </div>
          )}

          {lastToolResult?.ticket_id && (
            <div className="bg-white border border-[#E2E8F0] rounded-lg p-3 space-y-3 shadow-xs">
              <div className="flex items-center gap-2">
                <Ticket className="w-4 h-4 text-[#E30613] flex-shrink-0" />
                <p className="text-xs font-bold text-[#1E293B] uppercase tracking-wider">Ticket Created</p>
                <span className="ml-auto inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-green-50 text-green-700 border border-green-200 uppercase tracking-wider">
                  Created
                </span>
              </div>

              <div className="space-y-1.5 pt-1 border-t border-[#E2E8F0]">
                {[
                  { label: "Ticket ID", value: lastToolResult.ticket_id as string },
                  { label: "Assigned Team", value: (lastToolResult.assigned_team as string) ?? "IT Support" },
                  { label: "Priority", value: (lastToolResult.priority as string) ?? "Medium" },
                  { label: "Estimated SLA", value: `${lastToolResult.sla_hours ?? 4} Hours` },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center">
                    <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider">{label}</span>
                    <span className={`text-[10px] font-bold ${label === "Ticket ID" ? "text-[#E30613] font-mono" : "text-[#334155]"}`}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#F8FAFC] overflow-hidden font-sans">

      {/* Header */}
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
          <button
            onClick={() => setIsInvestigationOpen(true)}
            className="lg:hidden inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl transition-all cursor-pointer"
          >
            <Brain className="w-3.5 h-3.5 text-[#E30613]" />
            Status
          </button>

          {sessionId && (
            <button
              onClick={startNewSession}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-[#F1F5F9] text-xs font-bold text-[#475569] rounded-xl transition-all cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              New Session
            </button>
          )}
        </div>
      </div>

      {/* Two-column Body */}
      <div className="flex-1 min-h-0 flex overflow-hidden">

        {/* LEFT — CHAT AREA */}
        <div className="flex-1 min-w-0 flex flex-col border-r border-[#E2E8F0] bg-white">
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
                              <div className="flex items-center justify-between text-[10px] font-bold text-[#64748B]">
                                <span className="uppercase text-[#E30613] tracking-wider">Troubleshooting Step {details.stepNumber}</span>
                                <span className="uppercase tracking-wider">Step {details.stepNumber} of {totalSteps}</span>
                              </div>
                              <div className="w-full bg-[#F1F5F9] rounded-full h-1.5">
                                <div
                                  className="bg-[#E30613] h-1.5 rounded-full transition-all duration-300"
                                  style={{ width: `${(details.stepNumber / totalSteps) * 100}%` }}
                                />
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
                                <span className="text-xs font-bold text-[#1E293B]">
                                  {details.stepNumber === 1 ? "Have you completed this step?" : "Did that work?"}
                                </span>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => sendMessage("yes")}
                                    className="px-3.5 py-1.5 bg-[#16A34A] hover:bg-green-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                                  >
                                    ✔ Completed
                                  </button>
                                  <button
                                    onClick={() => sendMessage("no")}
                                    className="px-3.5 py-1.5 bg-[#F8FAFC] hover:bg-[#F1F5F9] text-[#475569] text-xs font-bold rounded-lg cursor-pointer transition-colors border border-[#E2E8F0]"
                                  >
                                    ❌ Still Not Working
                                  </button>
                                </div>
                              </div>
                            </div>
                          );
                        })()
                      ) : msg.type === "verification" ? (
                        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4 max-w-md w-full text-left">
                          <div className="flex items-center gap-2">
                            <Brain className="w-5 h-5 text-[#E30613] flex-shrink-0" />
                            <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Solution Verification</span>
                          </div>
                          <p className="text-xs text-[#334155] leading-relaxed font-semibold">
                            {msg.text}
                          </p>
                          <div className="pt-2 border-t border-[#E2E8F0] flex gap-3">
                            <button
                              onClick={() => sendMessage("yes")}
                              className="flex-1 py-2 bg-[#16A34A] hover:bg-green-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                            >
                              ✔ Yes, Solved
                            </button>
                            <button
                              onClick={() => sendMessage("no")}
                              className="flex-1 py-2 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                            >
                              ❌ No, Still Broken
                            </button>
                          </div>
                        </div>
                      ) : msg.type === "ticket_confirmation" ? (
                        <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4 max-w-md w-full text-left">
                          <div className="flex items-center gap-2">
                            <Ticket className="w-5 h-5 text-amber-500 flex-shrink-0" />
                            <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">ServiceNow Ticket Approval</span>
                          </div>
                          <p className="text-xs text-[#334155] leading-relaxed font-semibold">
                            I can create a ServiceNow ticket. Would you like me to proceed?
                          </p>
                          <div className="pt-2 border-t border-[#E2E8F0] flex gap-3">
                            <button
                              onClick={() => sendMessage("yes")}
                              className="flex-1 py-2 bg-[#E30613] hover:bg-red-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                            >
                              Create Ticket
                            </button>
                            <button
                              onClick={() => sendMessage("no")}
                              className="flex-1 py-2 bg-[#F8FAFC] hover:bg-[#F1F5F9] text-[#475569] text-xs font-bold rounded-lg cursor-pointer transition-colors border border-[#E2E8F0]"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : msg.type === "ticket_created" ? (
                        (() => {
                          const tr = msg.tool_result ?? {};
                          const ticket = tr.ticket ?? tr;
                          const requiresApproval = tr.requires_approval || ticket.requires_approval;
                          const requestType = tr.request_type || ticket.request_type || "INCIDENT";
                          const statusLabel = tr.ticket_status_label || ticket.status_label || (requiresApproval ? "Pending Manager Approval" : "Open — Assigned to IT Team");
                          const isServiceRequest = requestType === "SERVICE_REQUEST" || requiresApproval;
                          return (
                            <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-sm space-y-4 max-w-md w-full text-left">
                              <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-3">
                                <Ticket className="w-5 h-5 text-[#E30613] flex-shrink-0" />
                                <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">
                                  {isServiceRequest ? "Service Request Created" : "Support Ticket Created"}
                                </span>
                                <span className={`ml-auto inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${isServiceRequest
                                    ? "bg-amber-50 text-amber-800 border-amber-200"
                                    : "bg-green-50 text-green-700 border-green-200"
                                  }`}>
                                  {isServiceRequest ? "⏳ Pending Approval" : "✅ Active"}
                                </span>
                              </div>
                              <div className="grid grid-cols-2 gap-y-3 gap-x-4">
                                {[
                                  { label: "Ticket Number", value: tr.ticket_id || ticket.ticket_id || "Pending", highlight: true },
                                  { label: "Type", value: requestType.replace("_", " ") },
                                  { label: "Assigned Team", value: ticket.assigned_team || tr.assigned_team || "IT Operations" },
                                  { label: "Priority", value: ticket.priority || tr.priority || "Medium" },
                                  { label: "Estimated SLA", value: (ticket.sla_hours || tr.sla_hours) ? `${ticket.sla_hours || tr.sla_hours} Hours` : "4 Hours" },
                                  { label: "Status", value: statusLabel },
                                ].map(({ label, value, highlight }) => (
                                  <div key={label} className="space-y-0.5">
                                    <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider block">{label}</span>
                                    <span className={`text-xs font-bold ${highlight ? "text-[#E30613] font-mono" : "text-[#1E293B]"}`}>
                                      {value}
                                    </span>
                                  </div>
                                ))}
                              </div>
                              {isServiceRequest && (
                                <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-[11px] text-amber-800 font-bold">
                                  ⚠️ This request is pending your manager's approval. You'll be notified when it's approved.
                                </div>
                              )}
                              <p className="text-[10px] text-[#64748B] uppercase tracking-wider pt-1 font-bold">
                                Track status in <span className="text-[#1E293B]">My Tickets</span>
                              </p>
                            </div>
                          );
                        })()
                      ) : msg.type === "resolved" ? (
                        <div className="bg-green-50 border border-green-255 rounded-2xl p-5 shadow-sm space-y-3 max-w-md w-full text-left">
                          <div className="flex items-center gap-2.5">
                            <div className="w-6 h-6 rounded-full bg-green-100 border border-green-200 flex items-center justify-center flex-shrink-0">
                              <CheckCircle className="w-3.5 h-3.5 text-green-600" />
                            </div>
                            <h3 className="text-xs font-bold text-green-800 uppercase tracking-wider">Resolved</h3>
                          </div>
                          <p className="text-xs text-green-700 leading-relaxed font-semibold">
                            Problem solved successfully. Thank you for utilizing Bridgestone IT Automated Support.
                          </p>
                        </div>
                      ) : (
                        <div
                          className="bg-[#F8FAFC] border border-[#E2E8F0] text-[#1E293B] rounded-2xl rounded-bl-sm px-4 py-2.5 text-xs leading-relaxed font-semibold"
                        >
                          <span className="whitespace-pre-wrap">{msg.text}</span>
                        </div>
                      )}
                    </div>

                    {isUser && (
                      <div className="w-6 h-6 rounded-full bg-[#E2E8F0] flex items-center justify-center flex-shrink-0 mb-0.5">
                        <span className="text-[9px] font-bold text-[#475569] uppercase">
                          {username.charAt(0)}
                        </span>
                      </div>
                    )}
                  </div>
                );
              });
            }, [messages, username, msgTimes, setZoomImage])}

            {/* Loading / Typing */}
            {isLoading && (
              <div className="flex items-end gap-2.5">
                <div className="w-6 h-6 rounded-full bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center flex-shrink-0">
                  <Brain className="w-3 h-3 text-[#E30613]" />
                </div>
                <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 text-[#E30613] animate-spin" />
                    <span className="text-xs text-[#64748B] font-bold uppercase tracking-wider">Investigating your issue...</span>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-[#DC2626] font-bold">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Approval dialog */}
            {approvalRequired && approvalStatus === "PENDING" && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <span className="text-xs font-bold text-gray-805 uppercase tracking-wider">Your Approval Required</span>
                  <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300">
                    Pending
                  </span>
                </div>
                <p className="text-xs text-[#475569] font-medium leading-relaxed">
                  Proceed with:{" "}
                  <code className="font-mono font-bold text-[#E30613] bg-white px-1.5 py-0.5 rounded border border-[#E2E8F0]">
                    {recommendedAction}
                  </code>
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => sendMessage("yes")}
                    className="flex-1 py-2 bg-[#16A34A] hover:bg-green-700 text-white text-xs font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => sendMessage("no")}
                    className="flex-1 py-2 bg-[#F8FAFC] hover:bg-[#F1F5F9] text-[#475569] border border-[#E2E8F0] text-xs font-bold rounded-lg cursor-pointer transition-colors"
                  >
                    ✕ Decline
                  </button>
                </div>
              </div>
            )}

            {/* Context Actions list */}
            {actions.length > 0 && (
              <div className="flex gap-2 justify-end flex-wrap pt-1">
                {actions.map(act => (
                  <button
                    key={act}
                    onClick={() => sendMessage(act)}
                    className={`px-3.5 py-2 text-xs font-bold rounded-lg cursor-pointer transition-all border ${act === "SOLVED"
                      ? "bg-green-50 border-green-200 text-[#16A34A] hover:bg-green-100"
                      : act === "NOT_SOLVED"
                        ? "bg-[#F8FAFC] border-[#E2E8F0] text-[#475569] hover:bg-[#F1F5F9]"
                        : "bg-white border-[#E2E8F0] text-[#475569] hover:text-[#E30613] hover:border-[#FCA5A5]"
                      }`}
                  >
                    {act === "SOLVED" ? "✓ Issue Resolved" : act === "NOT_SOLVED" ? "Still Not Working" : act}
                  </button>
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* User Input controls */}
          {showInput && (
            <div className="flex-shrink-0 px-4 py-3 border-t border-[#E2E8F0] bg-white">
              <div className="flex items-center gap-2 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl px-3 py-2 focus-within:border-[#E30613]/30 focus-within:bg-white transition-all">
                <button
                  className="p-1 rounded text-gray-300 hover:text-gray-400 transition-colors cursor-not-allowed"
                  title="Attach file (coming soon)"
                  disabled
                  type="button"
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
                  className="flex items-center justify-center w-7 h-7 rounded-lg bg-[#E30613] hover:bg-red-700 disabled:bg-[#E2E8F0] text-white transition-colors cursor-pointer flex-shrink-0 shadow-xs"
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

        {/* Mobile Investigation status drawer overlay */}
        {isInvestigationOpen && (
          <div
            onClick={() => setIsInvestigationOpen(false)}
            className="lg:hidden fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-40 transition-opacity duration-200"
          />
        )}
        <aside
          className={`fixed inset-y-0 right-0 z-50 w-72 bg-white border-l border-[#E2E8F0] flex flex-col shadow-xl transform transition-transform duration-350 ease-in-out lg:hidden ${isInvestigationOpen ? "translate-x-0" : "translate-x-full"
            }`}
        >
          {renderInvestigationStatus()}
        </aside>

        {/* RIGHT — INVESTIGATION STATUS PANEL (DESKTOP) */}
        <div className="w-64 flex-shrink-0 flex flex-col bg-[#F8FAFC] border-l border-[#E2E8F0] overflow-hidden lg:flex hidden">
          {renderInvestigationStatus()}
        </div>

      </div>

      {zoomImage && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-xs z-50 flex items-center justify-center p-4 cursor-zoom-out"
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
