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
  const [currentStep, setCurrentStep] = useState(-1);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full min-h-[500px]">
      
      {/* ── LEFT COLUMN: Conversation ── */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm flex flex-col justify-between h-full">
        <div className="px-5 py-3 border-b border-gray-150 bg-gray-50/50 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-brand-red" />
            <span className="text-xs font-bold text-gray-800 uppercase">AI Dialogue</span>
          </div>
          {sessionId && (
            <button
              onClick={startNewSession}
              className="text-brand-red hover:text-brand-red-hover transition-colors text-[10px] font-bold flex items-center gap-1 cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" /> New Chat
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-gray-50/20">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-5 max-w-xs mx-auto">
              <div className="w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center border border-red-100">
                <Sparkles className="w-6 h-6 text-brand-red animate-pulse" />
              </div>
              <div>
                <span className="text-xs font-bold text-gray-800 block">Enterprise AI Assistant</span>
                <span className="text-[10.5px] text-gray-450 mt-1 block">Describe your request in natural language. The AI will reason, plan, and execute.</span>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"} animate-fade-in`}>
                <div className={`max-w-[90%] rounded-xl px-3.5 py-2.5 text-xs border shadow-sm ${
                  msg.sender === "user"
                    ? "bg-brand-red border-red-650 text-white rounded-br-none"
                    : "bg-white border-gray-200 text-gray-800 rounded-bl-none"
                }`}>
                  <span className="text-[8.5px] uppercase font-bold tracking-wide opacity-50 block mb-1">
                    {msg.sender === "user" ? username : "AI Engineer"}
                  </span>
                  <span className="whitespace-pre-wrap font-medium">{msg.text}</span>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-3 border-t border-gray-150 bg-gray-50/50">
          {actions.length === 0 && (!approvalRequired || approvalStatus !== "PENDING") && (
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(message);
                  }
                }}
                disabled={isLoading}
                placeholder="Ask AI (e.g. Install 7-Zip Security Utility)..."
                className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-brand-red focus:border-brand-red transition-all"
              />
              <button
                onClick={() => sendMessage(message)}
                disabled={isLoading || !message.trim()}
                className="bg-brand-red hover:bg-brand-red-hover disabled:bg-gray-250 text-white p-2 rounded-lg transition-colors flex items-center justify-center cursor-pointer flex-shrink-0"
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
                  className="px-3 py-1.5 bg-white border border-gray-200 text-gray-700 hover:text-brand-red hover:border-brand-red/30 text-[10.5px] font-bold rounded-lg cursor-pointer transition-all shadow-sm"
                >
                  {act === "SOLVED" ? "Mark Solved" : act === "NOT_SOLVED" ? "Not Resolved" : act}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── CENTER COLUMN: Reasoning Timeline (Exactly 9 steps) ── */}
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm flex flex-col gap-4 h-full">
        <div className="flex items-center gap-2 border-b border-gray-100 pb-2">
          <Sparkles className="w-4 h-4 text-brand-red" />
          <span className="text-xs font-bold text-gray-800 uppercase">Reasoning Pipeline</span>
        </div>

        <div className="flex-1 flex flex-col justify-center max-w-xs mx-auto w-full space-y-3.5">
          {reasoningSteps.map((step, sIdx) => {
            const isDone = currentStep > sIdx;
            const isActive = currentStep === sIdx;
            const isPending = currentStep < sIdx;

            return (
              <div key={step} className="flex items-center gap-3 relative">
                {sIdx < reasoningSteps.length - 1 && (
                  <div className={`absolute left-3.5 top-6 bottom-0 w-0.5 -mb-6 transition-all duration-300 ${
                    isDone ? "bg-green-500" : "bg-gray-200"
                  }`} />
                )}

                <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all flex-shrink-0 ${
                  isDone ? "bg-green-550 border-green-600 text-white" :
                  isActive ? "bg-red-50 border-brand-red text-brand-red animate-pulse scale-105" :
                  "bg-white border-gray-200 text-gray-300"
                }`}>
                  {isDone ? (
                    <Check className="w-4 h-4" />
                  ) : isActive ? (
                    <Loader2 className="w-3.5 h-3.5 text-brand-red animate-spin" />
                  ) : (
                    <span className="text-[10px] font-bold">{sIdx + 1}</span>
                  )}
                </div>

                <div className="flex flex-col">
                  <span className={`text-xs font-bold ${
                    isDone ? "text-gray-400 font-semibold" :
                    isActive ? "text-brand-red" :
                    "text-gray-400"
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
      <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm flex flex-col justify-between h-full">
        <div className="space-y-5">
          <div className="flex items-center justify-between border-b border-gray-100 pb-2">
            <span className="text-xs font-bold text-gray-800 uppercase block">Execution Plan</span>
            <span className={`badge ${
              currentStep === 8 ? "badge-healthy" :
              currentStep >= 5 ? "badge-in-progress" :
              currentStep >= 0 ? "badge-waiting" :
              "badge-closed"
            }`}>
              {currentStep === 8 ? "Completed" : currentStep >= 5 ? "Executing" : currentStep >= 0 ? "Queued" : "Idle"}
            </span>
          </div>

          {/* Checklist milestones */}
          <div className="space-y-3.5 text-xs text-gray-650 font-semibold">
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
                    isChecking ? "bg-red-50/30 border-brand-red/20 animate-pulse" :
                    "bg-white border-gray-150"
                  }`}
                >
                  {isChecked ? (
                    <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
                  ) : isChecking ? (
                    <Loader2 className="w-4 h-4 text-brand-red animate-spin flex-shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-gray-200 bg-gray-50 flex-shrink-0" />
                  )}
                  <span className={isChecked ? "text-gray-450 font-medium" : "text-gray-700"}>{st.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Approval Card */}
        <div className="pt-4">
          {approvalRequired && approvalStatus === "PENDING" ? (
            <div className="p-4 bg-red-50/50 border border-brand-red/15 rounded-xl space-y-3 shadow-sm animate-fade-in">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-gray-800 flex items-center gap-1.5">
                  <Shield className="w-4 h-4 text-brand-red" />
                  Authorization Requested
                </span>
                <span className="badge badge-waiting">Pending</span>
              </div>
              <p className="text-[10.5px] text-gray-600 leading-normal font-semibold">
                Approved execution required for: <code className="font-mono text-brand-red bg-white px-2 py-0.5 rounded border border-gray-200 block mt-1 font-bold">{recommendedAction}</code>
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => sendMessage("yes")}
                  className="flex-1 py-2 bg-green-650 hover:bg-green-600 text-white text-[10.5px] font-bold rounded-lg cursor-pointer transition-colors shadow-sm"
                >
                  Approve
                </button>
                <button
                  onClick={() => sendMessage("no")}
                  className="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white text-[10.5px] font-bold rounded-lg cursor-pointer transition-colors shadow-sm"
                >
                  Reject
                </button>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl text-[10.5px] text-gray-400 italic text-center font-medium">
              No authorization pending.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
