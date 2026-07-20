"use client";

import React from "react";
import { Search } from "lucide-react";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: string;
  children: React.ReactNode;
}

export function Badge({ variant = "DEFAULT", children, className = "", ...props }: BadgeProps) {
  const baseClass = "inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-bold uppercase tracking-wider whitespace-nowrap";
  
  let colorClass = "";
  const safeVariant = variant || "DEFAULT";
  const norm = safeVariant.toUpperCase().trim().replace(/\s+/g, "_");
  
  switch (norm) {
    case "NEW":
      colorClass = "bg-blue-50 text-blue-800 border-blue-200";
      break;
    case "IN_PROGRESS":
    case "ASSIGNED":
    case "RUNNING":
    case "AI_DIAGNOSING":
      colorClass = "bg-indigo-50 text-indigo-800 border-indigo-200";
      break;
    case "PENDING":
    case "WAITING":
      colorClass = "bg-amber-50 text-amber-800 border-amber-200";
      break;
    case "ADMIN_REQUIRED":
      colorClass = "bg-orange-100 text-orange-900 border-orange-300 font-extrabold";
      break;
    case "WAITING_MANAGER":
    case "WAITING_MANAGER_APPROVAL":
      colorClass = "bg-orange-50 text-orange-800 border-orange-200";
      break;
    case "WAITING_ADMIN":
    case "WAITING_ADMIN_APPROVAL":
      colorClass = "bg-amber-100 text-amber-900 border-amber-300";
      break;
    case "TEMP_ADMIN_GRANTED":
    case "ADMIN_APPROVED":
      colorClass = "bg-emerald-100 text-emerald-900 border-emerald-300 font-extrabold";
      break;
    case "EXECUTING":
    case "EXECUTION_READY":
      colorClass = "bg-indigo-100 text-indigo-900 border-indigo-300";
      break;
    case "COMPLETED":
      colorClass = "bg-teal-100 text-teal-900 border-teal-300";
      break;
    case "WAITING_FOR_USER":
      colorClass = "bg-yellow-50 text-yellow-900 border-yellow-300";
      break;
    case "APPROVED":
      colorClass = "bg-green-50 text-green-800 border-green-200";
      break;
    case "REJECTED":
    case "FAILED":
    case "ERROR":
    case "UNHEALTHY":
    case "DEGRADED":
      colorClass = "bg-red-50 text-red-800 border-red-200";
      break;
    case "RESOLVED":
    case "FULFILLED":
    case "SUCCESS":
    case "HEALTHY":
    case "ONLINE":
      colorClass = "bg-emerald-50 text-emerald-800 border-emerald-200";
      break;
    case "CLOSED":
    case "OFFLINE":
    case "INACTIVE":
    case "CANCELLED":
      colorClass = "bg-gray-100 text-gray-700 border-gray-300";
      break;
    case "INCIDENT":
      colorClass = "bg-transparent text-blue-700 border-blue-400 border";
      break;
    case "PRIVILEGED_ACTION":
      colorClass = "bg-transparent text-red-700 border-red-400 border font-extrabold";
      break;
    case "SERVICE_REQUEST":
    case "SERVICE REQUEST":
      colorClass = "bg-transparent text-purple-750 border-purple-400 border";
      break;
    case "LOW":
      colorClass = "bg-green-50 text-green-850 border-green-200";
      break;
    case "MEDIUM":
      colorClass = "bg-amber-50 text-amber-850 border-amber-200";
      break;
    case "HIGH":
      colorClass = "bg-orange-50 text-orange-850 border-orange-200";
      break;
    case "CRITICAL":
      colorClass = "bg-red-50 text-red-850 border-red-200";
      break;
    default:
      colorClass = "bg-slate-100 text-slate-700 border-slate-200";
  }
  
  return (
    <span className={`${baseClass} ${colorClass} ${className}`} {...props}>
      {children}
    </span>
  );
}

export function StatusPill({ status = "NEW", className = "" }: { status?: string; className?: string }) {
  const safeStatus = status || "NEW";
  const label = safeStatus.replace(/_/g, " ");
  return (
    <Badge variant={safeStatus} className={className}>
      {label}
    </Badge>
  );
}

export function PriorityPill({ priority = "MEDIUM", className = "" }: { priority?: string; className?: string }) {
  const safePriority = priority || "MEDIUM";
  return (
    <Badge variant={safePriority} className={className}>
      {safePriority}
    </Badge>
  );
}

export function RequestTypePill({ type = "INCIDENT", className = "" }: { type?: string; className?: string }) {
  const safeType = type || "INCIDENT";
  const label = safeType.replace(/_/g, " ");
  return (
    <Badge variant={safeType} className={className}>
      {label}
    </Badge>
  );
}

export function ApprovalPill({ status = "PENDING", className = "" }: { status?: string; className?: string }) {
  const safeStatus = status || "PENDING";
  const label = safeStatus.replace(/_/g, " ");
  return (
    <Badge variant={safeStatus} className={className}>
      {label}
    </Badge>
  );
}

interface SearchInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  onSearch?: (val: string) => void;
}

export function SearchInput({ value, onChange, placeholder = "Search...", className = "", ...props }: SearchInputProps) {
  return (
    <div className="relative flex items-center w-full">
      <Search className="absolute left-3 w-4 h-4 text-gray-400 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`pl-9 pr-3 py-1.5 w-full text-xs font-semibold text-gray-800 placeholder-gray-400 bg-white border border-[#E2E8F0] rounded-xl outline-none focus:ring-2 focus:ring-[#E30613]/10 focus:border-[#E30613] transition-all ${className}`}
        {...props}
      />
    </div>
  );
}

export function Table({ children, className = "", ...props }: React.HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto border border-[#E2E8F0] rounded-xl bg-white shadow-xs">
      <table className={`w-full border-collapse text-xs text-left ${className}`} {...props}>
        {children}
      </table>
    </div>
  );
}

export function TableHeader({ children, className = "", ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={`bg-[#F8FAFC] border-b border-[#E2E8F0] ${className}`} {...props}>
      {children}
    </thead>
  );
}

export function TableHead({ children, className = "", ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={`px-5 py-3 text-[10px] font-semibold uppercase tracking-wide text-gray-700 whitespace-nowrap text-left ${className}`} {...props}>
      {children}
    </th>
  );
}

export function TableBody({ children, className = "", ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={`divide-y divide-[#E2E8F0] align-middle text-gray-800 ${className}`} {...props}>
      {children}
    </tbody>
  );
}

export function TableRow({ children, className = "", ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={`hover:bg-gray-50/80 transition-colors ${className}`} {...props}>
      {children}
    </tr>
  );
}

export function TableCell({ children, className = "", ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-5 py-3 whitespace-nowrap align-middle ${className}`} {...props}>
      {children}
    </td>
  );
}
