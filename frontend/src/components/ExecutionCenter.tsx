"use client";

import { useState, useEffect } from "react";
import { Terminal, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

interface ExecutionJob {
  id: string;
  name: string;
  target: string;
  status: "Running" | "Completed" | "Error";
  progress: number;
  currentStep: string;
  nextStep: string;
  eta: string;
}

export default function ExecutionCenter() {
  const [jobs, setJobs] = useState<ExecutionJob[]>([
    { id: "EXE-094", name: "Install 7-Zip Security Utility", target: "JP-TOK-EDG-001", status: "Running", progress: 65, currentStep: "Installing", nextStep: "Verification Check", eta: "12s" },
    { id: "EXE-093", name: "VPN Connection Refresh", target: "US-NSH-LPT-284", status: "Completed", progress: 100, currentStep: "Done", nextStep: "None", eta: "0s" },
    { id: "EXE-092", name: "SAP Role Revocation Action", target: "EU-BRU-SRV-049", status: "Error", progress: 45, currentStep: "API Connection Error", nextStep: "Escalation Check", eta: "—" }
  ]);

  // Animate demo progress
  useEffect(() => {
    const timer = setInterval(() => {
      setJobs(prevJobs => 
        prevJobs.map(job => {
          if (job.status === "Running" && job.progress < 100) {
            const nextProgress = job.progress + 5;
            if (nextProgress >= 100) {
              return { ...job, progress: 100, status: "Completed", currentStep: "Done", nextStep: "None", eta: "0s" };
            }
            return { ...job, progress: nextProgress };
          }
          return job;
        })
      );
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="pb-4 border-b border-gray-200">
        <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-brand-red" />
          Execution Center
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Monitor every autonomous operation executing on corporate endpoints.
        </p>
      </div>

      <div className="space-y-4">
        {jobs.map(job => (
          <div key={job.id} className="card p-5 bg-white border border-gray-250 flex flex-col gap-4">
            <div className="flex justify-between items-start gap-4">
              <div>
                <span className="text-[9.5px] font-mono text-gray-400 bg-gray-100 px-2 py-0.5 rounded font-bold">{job.id}</span>
                <h3 className="text-sm font-bold text-gray-800 mt-1.5">{job.name}</h3>
                <span className="text-[10px] text-gray-400 font-mono mt-0.5 block">Endpoint Asset: <strong className="text-gray-650 font-bold">{job.target}</strong></span>
              </div>
              <span className={`badge ${
                job.status === "Running" ? "badge-in-progress" : 
                job.status === "Completed" ? "badge-healthy" : "badge-unhealthy"
              }`}>{job.status}</span>
            </div>

            {/* Progress bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold text-gray-600">
                <span>Deployment Completion</span>
                <span>{job.progress}%</span>
              </div>
              <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-300 ${
                    job.status === "Completed" ? "bg-green-600" : job.status === "Error" ? "bg-red-650" : "bg-brand-red"
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </div>

            {/* Steps & ETA */}
            <div className="grid grid-cols-3 gap-4 pt-2 text-xs font-semibold text-gray-600">
              <div>
                <span className="text-[9px] text-gray-400 block font-bold">CURRENT STEP</span>
                <span className="text-gray-800 flex items-center gap-1.5 mt-1 font-bold">
                  {job.status === "Running" && <Loader2 className="w-3.5 h-3.5 text-brand-red animate-spin" />}
                  {job.currentStep}
                </span>
              </div>
              <div>
                <span className="text-[9px] text-gray-400 block font-bold">NEXT STEP</span>
                <span className="text-gray-700 mt-1 block font-medium">{job.nextStep}</span>
              </div>
              <div className="text-right">
                <span className="text-[9px] text-gray-400 block font-bold">ESTIMATED TIME</span>
                <span className="text-gray-850 mt-1 block font-mono font-bold">{job.eta}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
