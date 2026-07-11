"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Sparkles, User, RefreshCw, Check, Shield, 
  ArrowUpRight, Clock, Terminal, CheckCircle2, Loader2
} from "lucide-react";

interface Message {
  sender: "user" | "agent";
  text: string;
  category?: string;
  source?: string;
  context_used?: boolean;
  action?: string;
  tool_result?: Record<string, any> | null;
}

interface AiAssistantProps {
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

export default function AiAssistant({
  messages,
  message,
  setMessage,
  sendMessage,
  startNewSession,
  sessionId,
  isLoading,
  actions,
  approvalRequired,
  approvalStatus,
  recommendedAction,
  username
}: AiAssistantProps) {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [currentStep, setCurrentStep] = useState(-1);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!isLoading) {
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [messages.length, isLoading, approvalRequired, approvalStatus]);

  // Simulate progress through the 9 reasoning pipeline steps
  useEffect(() => {
    if (isLoading) {
      setCurrentStep(0);
      const timer = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev < 7) return prev + 1;
          clearInterval(timer);
          return prev;
        });
      }, 1000);
      return () => clearInterval(timer);
    } else {
      if (messages.length > 0) {
        setCurrentStep(8); // Completed
      } else {
        setCurrentStep(-1); // Reset
      }
    }
  }, [isLoading, messages]);

  const reasoningSteps = [
    "Goal Understood",
    "Checking Company Policy",
    "Searching Knowledge Base",
    "Checking Device",
    "Planning",
    "Waiting Approval",
    "Executing",
    "Verification",
    "Completed"
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full min-h-[500px] font-sans bg-[#F8FAFC]">
      
      {/* ── LEFT COLUMN: Conversation ── */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl overflow-hidden shadow-xs flex flex-col justify-between h-full">
        <div className="px-5 py-3 border-b border-[#E2E8F0] bg-[#F8FAFC] flex justify-between items-center">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-[#E30613]" />
            <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">AI Dialogue</span>
          </div>
          {sessionId && (
            <button
              onClick={startNewSession}
              className="text-[#E30613] hover:text-red-750 transition-colors text-[10px] font-bold flex items-center gap-1 cursor-pointer uppercase tracking-wider"
            >
              <RefreshCw className="w-3 h-3" /> New Chat
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-white">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-5 max-w-xs mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-[#FEF2F2] border border-[#FEE2E2] flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-[#E30613]" />
              </div>
              <div>
                <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Enterprise AI Assistant</span>
                <span className="text-[10.5px] text-[#64748B] font-semibold mt-1 block leading-normal uppercase">Describe your request in natural language. The AI will reason, plan, and execute.</span>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} animate-fade-in`}>
                <div className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-xs border shadow-xs ${
                  msg.sender === "user"
                    ? "bg-[#E30613] border-red-750 text-white rounded-br-none"
                    : "bg-[#F8FAFC] border-[#E2E8F0] text-[#1E293B] rounded-bl-none font-semibold"
                }`}>
                  <span className="text-[8.5px] uppercase font-bold tracking-wide opacity-80 block mb-1">
                    {msg.sender === "user" ? username : "AI Engineer"}
                  </span>
                  <span className="whitespace-pre-wrap">
                    {msg.sender === "user" 
                      ? msg.text 
                      : msg.text.replace(/\[Screenshot:\s*([^\s\]]+)(?:\s*[-—]\s*([^\]]+))?\]/i, "").replace(/[^\[\s]+\.png/g, "").trim()}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-3 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          {actions.length === 0 && (!approvalRequired || approvalStatus !== "PENDING") && (
            <div className="flex gap-2 items-center">
              <input
                ref={inputRef}
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (message.trim()) sendMessage(message);
                  }
                }}
                disabled={isLoading}
                placeholder="Ask AI (e.g. Install 7-Zip Security Utility)..."
                className="w-full bg-white border border-[#E2E8F0] rounded-xl px-3 py-2 text-xs text-[#1E293B] font-semibold placeholder-[#94A3B8] focus:outline-none focus:ring-1 focus:ring-[#E30613]"
              />
              <button
                onClick={() => sendMessage(message)}
                disabled={isLoading || !message.trim()}
                className="bg-[#E30613] hover:bg-red-700 disabled:bg-[#E2E8F0] text-white p-2 rounded-xl transition-colors flex items-center justify-center cursor-pointer flex-shrink-0"
              >
                <ArrowUpRight className="h-4.5 w-4.5" />
              </button>
            </div>
          )}

          {actions.length > 0 && (
            <div className="flex gap-2 justify-end">
              {actions.map((act) => (
                <button
                  key={act}
                  onClick={() => sendMessage(act)}
                  className="px-3 py-1.5 bg-white border border-[#E2E8F0] text-[#475569] hover:text-[#E30613] hover:border-[#FCA5A5] text-[10.5px] font-bold rounded-lg cursor-pointer transition-all shadow-xs"
                >
                  {act === "SOLVED" ? "Mark Solved" : act === "NOT_SOLVED" ? "Not Resolved" : act}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── CENTER COLUMN: Reasoning Pipeline (Exactly 9 steps) ── */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs flex flex-col gap-4 h-full">
        <div className="flex items-center gap-2 border-b border-[#E2E8F0] pb-2">
          <Sparkles className="w-4 h-4 text-[#E30613]" />
          <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider">Reasoning Pipeline</span>
        </div>

        <div className="flex-1 flex flex-col justify-center max-w-xs mx-auto w-full space-y-3.5">
          {reasoningSteps.map((step, sIdx) => {
            const isDone = currentStep > sIdx;
            const isActive = currentStep === sIdx;

            return (
              <div key={step} className="flex items-center gap-3 relative">
                {sIdx < reasoningSteps.length - 1 && (
                  <div className={`absolute left-3.5 top-6 bottom-0 w-0.5 -mb-6 transition-all duration-300 ${
                    isDone ? "bg-green-550" : "bg-[#E2E8F0]"
                  }`} />
                )}

                <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all flex-shrink-0 ${
                  isDone ? "bg-green-600 border-green-700 text-white" :
                  isActive ? "bg-[#FEF2F2] border-[#E30613] text-[#E30613] animate-pulse scale-105" :
                  "bg-white border-[#E2E8F0] text-[#94A3B8]"
                }`}>
                  {isDone ? (
                    <Check className="w-4 h-4" />
                  ) : isActive ? (
                    <Loader2 className="w-3.5 h-3.5 text-[#E30613] animate-spin" />
                  ) : (
                    <span className="text-[10px] font-bold">{sIdx + 1}</span>
                  )}
                </div>

                <div className="flex flex-col">
                  <span className={`text-xs font-bold ${
                    isDone ? "text-[#94A3B8]" :
                    isActive ? "text-[#E30613]" :
                    "text-[#64748B]"
                  }`}>
                    {step}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── RIGHT COLUMN: Execution Plan & Status Badges ── */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-5 shadow-xs flex flex-col justify-between h-full">
        <div className="space-y-5">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-2">
            <span className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Execution Plan</span>
            <span className={`badge border ${
              currentStep === 8 ? "badge-success" :
              currentStep >= 5 ? "badge-updating" :
              currentStep >= 0 ? "badge-pending" :
              "badge-failed"
            }`}>
              {currentStep === 8 ? "Completed" : currentStep >= 5 ? "Executing" : currentStep >= 0 ? "Queued" : "Idle"}
            </span>
          </div>

          {/* Checklist milestones */}
          <div className="space-y-3.5 text-xs text-[#475569] font-bold">
            {[
              { label: "Policy Check", runIdx: 1 },
              { label: "Catalog Verification", runIdx: 2 },
              { label: "Storage Check", runIdx: 3 },
              { label: "Execute", runIdx: 6 },
              { label: "Verify", runIdx: 7 },
              { label: "Notify", runIdx: 8 }
            ].map(st => {
              const isChecked = currentStep >= st.runIdx;
              const isChecking = currentStep === st.runIdx - 1;
              return (
                <div 
                  key={st.label} 
                  className={`flex items-center gap-2.5 p-2 rounded-lg border transition-all ${
                    isChecked ? "bg-green-50/20 border-green-200" :
                    isChecking ? "bg-red-50/30 border-[#E30613]/20 animate-pulse" :
                    "bg-white border-[#E2E8F0]"
                  }`}
                >
                  {isChecked ? (
                    <CheckCircle2 className="w-4 h-4 text-[#16A34A] flex-shrink-0" />
                  ) : isChecking ? (
                    <Loader2 className="w-4 h-4 text-[#E30613] animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-[#E2E8F0] bg-[#F8FAFC] flex-shrink-0" />
                  )}
                  <span className={isChecked ? "text-[#94A3B8] font-medium" : "text-[#475569]"}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Approval Card */}
        <div className="pt-4">
          {approvalRequired && approvalStatus === "PENDING" ? (
            <div className="p-4 bg-[#FFFBEB] border border-amber-250 rounded-xl space-y-3 shadow-xs animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-[#92400E] flex items-center gap-1.5 uppercase tracking-wider">
                  <Shield className="w-4 h-4 text-[#E30613]" />
                  Authorization Requested
                </span>
                <span className="badge border badge-pending">Pending</span>
              </div>
              <p className="text-[10.5px] text-[#92400E] leading-normal font-semibold">
                Approved execution required for: <code className="font-mono text-[#E30613] bg-white px-2 py-0.5 rounded border border-[#E2E8F0] block mt-1 font-bold">{recommendedAction}</code>
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => sendMessage("yes")}
                  className="flex-1 py-2 bg-[#16A34A] hover:bg-green-700 text-white text-[10.5px] font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                >
                  Approve
                </button>
                <button
                  onClick={() => sendMessage("no")}
                  className="flex-1 py-2 bg-[#E30613] hover:bg-red-700 text-white text-[10.5px] font-bold rounded-lg cursor-pointer transition-colors shadow-xs"
                >
                  Reject
                </button>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-[10px] text-[#64748B] font-bold uppercase tracking-wider text-center">
              No authorization pending.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
