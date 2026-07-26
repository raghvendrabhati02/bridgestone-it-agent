"use client";

import React, { useState, useEffect } from "react";
import { Shield, Eye, EyeOff, Copy, Check, Clock, AlertTriangle } from "lucide-react";

interface EnterpriseAdminAccessCardProps {
  username?: string;
  password?: string;
  expiresAt?: string | null;
  validForMinutes?: number;
  source?: string;
  className?: string;
}

export default function EnterpriseAdminAccessCard({
  username = ".\\Administrator",
  password = "Temp@4821#",
  expiresAt,
  validForMinutes = 15,
  source = "Mock Enterprise Integration",
  className = "",
}: EnterpriseAdminAccessCardProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [copiedPass, setCopiedPass] = useState(false);

  // Calculate initial remaining seconds
  const calculateRemaining = () => {
    if (expiresAt) {
      const expTime = new Date(expiresAt).getTime();
      const now = Date.now();
      const diff = Math.floor((expTime - now) / 1000);
      return diff > 0 ? diff : 0;
    }
    return validForMinutes * 60; // fallback to 15 mins (900s)
  };

  const [remainingSeconds, setRemainingSeconds] = useState<number>(calculateRemaining);

  useEffect(() => {
    setRemainingSeconds(calculateRemaining());
  }, [expiresAt]);

  // Dynamic Ticking Timer
  useEffect(() => {
    if (remainingSeconds <= 0) return;

    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setShowPassword(false); // Hide password automatically when expired
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [remainingSeconds]);

  const isExpired = remainingSeconds <= 0;

  // Format MM:SS
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const handleCopyUser = () => {
    navigator.clipboard.writeText(username);
    setCopiedUser(true);
    setTimeout(() => setCopiedUser(false), 2000);
  };

  const handleCopyPass = () => {
    if (isExpired) return;
    navigator.clipboard.writeText(password);
    setCopiedPass(true);
    setTimeout(() => setCopiedPass(false), 2000);
  };

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border shadow-xl transition-all duration-300 font-sans ${
        isExpired
          ? "bg-slate-950 border-red-900/60 shadow-red-950/20"
          : "bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 border-indigo-500/40 shadow-indigo-950/30"
      } ${className}`}
    >
      {/* Top Decorative Accent Line */}
      <div
        className={`h-1.5 w-full ${
          isExpired
            ? "bg-gradient-to-r from-red-600 via-rose-500 to-red-700"
            : "bg-gradient-to-r from-emerald-400 via-teal-300 to-indigo-500"
        }`}
      />

      <div className="p-5 space-y-4">
        {/* Banner Section */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 flex items-start gap-3 shadow-inner">
          <div
            className={`p-2 rounded-lg border flex-shrink-0 ${
              isExpired
                ? "bg-red-950/50 border-red-800/40 text-red-400"
                : "bg-emerald-950/50 border-emerald-800/40 text-emerald-400"
            }`}
          >
            {isExpired ? <AlertTriangle className="w-5 h-5" /> : <Shield className="w-5 h-5 animate-pulse" />}
          </div>
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-extrabold text-white block tracking-wide uppercase">
              Temporary administrator credentials generated.
            </span>
            <span className="text-[10px] text-amber-400 font-mono font-bold block mt-1 tracking-tight">
              TODO: Replace with CyberArk / Windows LAPS / Azure PIM
            </span>
          </div>
        </div>

        {/* Status & Metadata Bar */}
        <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Status:</span>
            {isExpired ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-red-950/80 border border-red-700/60 text-red-400 uppercase tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                EXPIRED
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 uppercase tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                ACTIVE
              </span>
            )}
          </div>

          <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            <span>Valid For:</span>
            <span className="text-white font-mono">{validForMinutes} Minutes</span>
          </div>
        </div>

        {/* Main Credentials Display */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
          {/* Username Field */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 space-y-1.5">
            <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">Username</span>
            <div className="flex items-center justify-between bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 font-mono text-xs text-white">
              <span className="truncate select-all">{username}</span>
              <button
                type="button"
                onClick={handleCopyUser}
                className="ml-2 text-slate-400 hover:text-white transition cursor-pointer p-1"
                title="Copy username"
              >
                {copiedUser ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Password Field */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Password</span>
              {!isExpired && (
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 transition cursor-pointer flex items-center gap-1 uppercase tracking-wider"
                >
                  {showPassword ? (
                    <>
                      <EyeOff className="w-3 h-3" /> Hide Password
                    </>
                  ) : (
                    <>
                      <Eye className="w-3 h-3" /> Show Password
                    </>
                  )}
                </button>
              )}
            </div>

            <div className="flex items-center justify-between bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 font-mono text-xs">
              {isExpired ? (
                <span className="text-slate-600 select-none">••••••••••••</span>
              ) : showPassword ? (
                <span className="text-emerald-300 font-bold tracking-wider select-all">{password}</span>
              ) : (
                <span className="text-slate-500 tracking-widest select-none">••••••••••••</span>
              )}

              {!isExpired && showPassword && (
                <button
                  type="button"
                  onClick={handleCopyPass}
                  className="ml-2 text-slate-400 hover:text-white transition cursor-pointer p-1"
                  title="Copy password"
                >
                  {copiedPass ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Footer Bar with Countdown Timer & Source */}
        <div className="flex flex-col sm:flex-row items-center justify-between pt-3 border-t border-slate-800/80 text-[10px] text-slate-400 gap-2">
          <div className="flex items-center gap-2">
            <span className="font-bold uppercase tracking-wider">Countdown Timer:</span>
            <span
              className={`font-mono text-sm font-black px-2.5 py-0.5 rounded border ${
                isExpired
                  ? "bg-red-950/60 border-red-800 text-red-500"
                  : remainingSeconds <= 180
                  ? "bg-amber-950/60 border-amber-800 text-amber-400 animate-pulse"
                  : "bg-indigo-950/60 border-indigo-800 text-emerald-400"
              }`}
            >
              {formatTime(remainingSeconds)}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-slate-500 font-medium">
            <span>Source:</span>
            <span className="text-slate-300 font-bold">{source}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
