<!DOCTYPE html>

<html lang="en">

<head>

&#x20;   <meta charset="UTF-8">

&#x20;   <meta name="viewport" content="width=device-width, initial-scale=1.0">

&#x20;   <title>Bridgestone Enterprise AI Service Desk Architecture</title>

&#x20;   <style>

&#x20;       body {

&#x20;           font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;

&#x20;           background-color: #f3f4f6;

&#x20;           margin: 0;

&#x20;           padding: 20px;

&#x20;           color: #333;

&#x20;       }

&#x20;       .container {

&#x20;           max-width: 1100px;

&#x20;           margin: 0 auto;

&#x20;           background: #ffffff;

&#x20;           padding: 30px;

&#x20;           border-radius: 8px;

&#x20;           box-shadow: 0 4px 6px rgba(0,0,0,0.05);

&#x20;       }

&#x20;       h1 {

&#x20;           color: #032d26;

&#x20;           border-bottom: 3px solid #0078d4;

&#x20;           padding-bottom: 10px;

&#x20;           margin-top: 0;

&#x20;           font-size: 26px;

&#x20;       }

&#x20;       h2 {

&#x20;           color: #0078d4;

&#x20;           font-size: 20px;

&#x20;           margin-top: 30px;

&#x20;           margin-bottom: 15px;

&#x20;       }

&#x20;       .description {

&#x20;           font-size: 14px;

&#x20;           color: #666;

&#x20;           margin-bottom: 20px;

&#x20;           line-height: 1.5;

&#x20;       }

&#x20;       .diagram-wrapper {

&#x20;           background: #fafafa;

&#x20;           border: 1px solid #e5e7eb;

&#x20;           border-radius: 6px;

&#x20;           padding: 20px;

&#x20;           overflow-x: auto;

&#x20;           text-align: center;

&#x20;       }

&#x20;       .legend {

&#x20;           display: flex;

&#x20;           gap: 20px;

&#x20;           margin-top: 15px;

&#x20;           font-size: 12px;

&#x20;           justify-content: center;

&#x20;       }

&#x20;       .legend-item {

&#x20;           display: flex;

&#x20;           align-items: center;

&#x20;           gap: 5px;

&#x20;       }

&#x20;       .legend-color {

&#x20;           width: 15px;

&#x20;           height: 15px;

&#x20;           border-radius: 3px;

&#x20;       }

&#x20;   </style>

</head>

<body>



<div class="container">

&#x20;   <h1>Bridgestone IT Service Desk — Enterprise Architecture Review</h1>

&#x20;   <p class="description"><strong>Review Board Note:</strong> These vector diagrams represent the high-availability, layered technical architecture and the granular cognitive reasoning engine designed to safely integrate LangGraph automation with our core ServiceNow ecosystem.</p>



&#x20;   <h2>Architecture 1: Layered Enterprise Technical Architecture</h2>

&#x20;   <div class="diagram-wrapper">

&#x20;       <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 760" width="100%">

&#x20;           <defs>

&#x20;               <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">

&#x20;                   <path d="M 0 1 L 10 5 L 0 9 z" fill="#4b5563"/>

&#x20;               </marker>

&#x20;           </defs>



&#x20;           <rect x="10" y="10" width="880" height="60" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>

&#x20;           <text x="30" y="46" font-size="14" font-weight="bold" fill="#334155">USERS</text>

&#x20;           <rect x="200" y="20" width="160" height="40" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"/>

&#x20;           <text x="280" y="45" font-size="13" text-anchor="middle" fill="#1e293b">Bridgestone Employee</text>

&#x20;           <rect x="400" y="20" width="160" height="40" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"/>

&#x20;           <text x="480" y="45" font-size="13" text-anchor="middle" fill="#1e293b">Manager / Approver</text>

&#x20;           <rect x="600" y="20" width="160" height="40" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"/>

&#x20;           <text x="680" y="45" font-size="13" text-anchor="middle" fill="#1e293b">IT Administrator</text>



&#x20;           <path d="M 450 70 L 450 90" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="90" width="880" height="70" rx="6" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1.5"/>

&#x20;           <text x="30" y="130" font-size="14" font-weight="bold" fill="#1e40af">PRESENTATION LAYER</text>

&#x20;           <g fill="#ffffff" stroke="#3b82f6" stroke-width="1" font-size="12" text-anchor="middle">

&#x20;               <rect x="230" y="105" width="130" height="40" rx="4"/><text x="295" y="129" fill="#1e3a8a">Next.js Portal</text>

&#x20;               <rect x="375" y="105" width="130" height="40" rx="4"/><text x="440" y="129" fill="#1e3a8a">Interactive Chat UI</text>

&#x20;               <rect x="520" y="105" width="130" height="40" rx="4"/><text x="585" y="129" fill="#1e3a8a">Exec Dashboard</text>

&#x20;               <rect x="665" y="105" width="130" height="40" rx="4"/><text x="730" y="129" fill="#1e3a8a">Monitoring UI</text>

&#x20;           </g>



&#x20;           <path d="M 450 160 L 450 180" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="200" y="180" width="500" height="30" rx="4" fill="#475569" stroke="#334155" stroke-width="1"/>

&#x20;           <text x="450" y="200" font-size="13" font-weight="bold" text-anchor="middle" fill="#ffffff">ENTERPRISE API GATEWAY</text>



&#x20;           <path d="M 450 210 L 450 230" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="230" width="880" height="70" rx="6" fill="#fff1f2" stroke="#fecdd3" stroke-width="1.5"/>

&#x20;           <text x="30" y="270" font-size="14" font-weight="bold" fill="#9f1239">SECURITY LAYER</text>

&#x20;           <g fill="#ffffff" stroke="#f43f5e" stroke-width="1" font-size="12" text-anchor="middle">

&#x20;               <rect x="230" y="245" width="110" height="40" rx="4"/><text x="285" y="269" fill="#4c0519">JWT Auth</text>

&#x20;               <rect x="355" y="245" width="110" height="40" rx="4"/><text x="410" y="269" fill="#4c0519">RBAC Engine</text>

&#x20;               <rect x="480" y="245" width="120" height="40" rx="4"/><text x="540" y="269" fill="#4c0519">Session Manager</text>

&#x20;               <rect x="615" y="245" width="110" height="40" rx="4"/><text x="670" y="269" fill="#4c0519">Rate Limiter</text>

&#x20;               <rect x="740" y="245" width="120" height="40" rx="4"/><text x="800" y="269" fill="#4c0519">Input Validation</text>

&#x20;           </g>



&#x20;           <path d="M 450 300 L 450 320" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="320" width="880" height="80" rx="6" fill="#f0fdf4" stroke="#bbf7d0" stroke-width="1.5"/>

&#x20;           <text x="30" y="365" font-size="14" font-weight="bold" fill="#166534">APPLICATION LAYER</text>

&#x20;           <g fill="#ffffff" stroke="#22c55e" stroke-width="1" font-size="11" text-anchor="middle">

&#x20;               <rect x="200" y="340" width="120" height="40" rx="4"/><text x="260" y="364" fill="#14532d">Conversation Svc</text>

&#x20;               <rect x="330" y="340" width="110" height="40" rx="4"/><text x="385" y="364" fill="#14532d">Ticket Service</text>

&#x20;               <rect x="450" y="340" width="110" height="40" rx="4"/><text x="505" y="364" fill="#14532d">SLA Monitor</text>

&#x20;               <rect x="570" y="340" width="110" height="40" rx="4"/><text x="625" y="364" fill="#14532d">Approval Workflow</text>

&#x20;               <rect x="695" y="340" width="110" height="40" rx="4"/><text x="750" y="364" fill="#14532d">Audit \& Analytics</text>

&#x20;               <rect x="812" y="340" width="70" height="40" rx="4"/><text x="847" y="364" fill="#14532d">Scheduler</text>

&#x20;           </g>



&#x20;           <path d="M 450 400 L 450 420" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="420" width="880" height="80" rx="6" fill="#faf5ff" stroke="#e9d5ff" stroke-width="1.5"/>

&#x20;           <text x="30" y="455" font-size="14" font-weight="bold" fill="#6b21a8">AI ORCHESTRATION</text>

&#x20;           <text x="30" y="475" font-size="11" fill="#7e22ce" font-style="italic">(LangGraph Agent Framework)</text>

&#x20;           <g fill="#ffffff" stroke="#a855f7" stroke-width="1" font-size="11" text-anchor="middle">

&#x20;               <rect x="200" y="440" width="100" height="40" rx="4" stroke-width="2" stroke="#6b21a8"/><text x="250" y="464" font-weight="bold" fill="#4c1d95">Intent Agent</text>

&#x20;               <rect x="310" y="440" width="110" height="40" rx="4"/><text x="365" y="464" fill="#4c1d95">Knowledge Agent</text>

&#x20;               <rect x="430" y="440" width="100" height="40" rx="4"/><text x="480" y="464" fill="#4c1d95">Planner Agent</text>

&#x20;               <rect x="540" y="440" width="110" height="40" rx="4"/><text x="595" y="464" fill="#4c1d95">Diagnostic Agent</text>

&#x20;               <rect x="660" y="440" width="110" height="40" rx="4"/><text x="715" y="464" fill="#4c1d95">Hypothesis Agent</text>

&#x20;               <rect x="780" y="440" width="100" height="40" rx="4"/><text x="830" y="464" fill="#4c1d95">Decision Agent</text>

&#x20;           </g>



&#x20;           <path d="M 450 500 L 450 520" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="520" width="880" height="70" rx="6" fill="#f0fdfa" stroke="#ccfbf1" stroke-width="1.5"/>

&#x20;           <text x="30" y="560" font-size="13" font-weight="bold" fill="#0f766e">ADAPTER LAYER</text>

&#x20;           <g fill="#ffffff" stroke="#14b8a6" stroke-width="1" font-size="11" text-anchor="middle">

&#x20;               <rect x="200" y="535" width="100" height="40" rx="4"/><text x="250" y="559" fill="#115e59">VPN / Network</text>

&#x20;               <rect x="310" y="535" width="100" height="40" rx="4"/><text x="360" y="559" fill="#115e59">Outlook / Exchange</text>

&#x20;               <rect x="420" y="535" width="110" height="40" rx="4"/><text x="475" y="559" fill="#115e59">Active Directory</text>

&#x20;               <rect x="540" y="535" width="110" height="40" rx="4"/><text x="595" y="559" fill="#115e59">Microsoft Graph</text>

&#x20;               <rect x="660" y="535" width="130" height="40" rx="4" stroke="#032d26" stroke-width="2"/><text x="725" y="559" font-weight="bold" fill="#032d26">ServiceNow Spoke</text>

&#x20;               <rect x="800" y="535" width="80" height="40" rx="4"/><text x="840" y="559" fill="#115e59">Teams/SMTP</text>

&#x20;           </g>



&#x20;           <path d="M 450 590 L 450 610" stroke="#4b5563" stroke-width="1.5" marker-end="url(#arrow)"/>



&#x20;           <rect x="10" y="610" width="540" height="140" rx="6" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>

&#x20;           <text x="30" y="640" font-size="14" font-weight="bold" fill="#334155">DATA LAYER</text>

&#x20;           

&#x20;           <rect x="150" y="630" width="110" height="45" rx="4" fill="#f1f5f9" stroke="#94a3b8" stroke-dasharray="3,3"/>

&#x20;           <text x="205" y="650" font-size="11" text-anchor="middle" fill="#64748b" font-weight="bold">SQLite</text>

&#x20;           <text x="205" y="665" font-size="10" text-anchor="middle" fill="#64748b">(Current POC Only)</text>



&#x20;           <rect x="280" y="630" width="120" height="45" rx="4" fill="#e0f2fe" stroke="#0288d1" stroke-width="1.5"/>

&#x20;           <text x="340" y="650" font-size="11" text-anchor="middle" fill="#01579b" font-weight="bold">PostgreSQL</text>

&#x20;           <text x="340" y="665" font-size="10" text-anchor="middle" fill="#01579b">(Prod Operational)</text>



&#x20;           <rect x="415" y="630" width="120" height="45" rx="4" fill="#fef2f2" stroke="#dc2626" stroke-width="1"/>

&#x20;           <text x="475" y="657" font-size="12" text-anchor="middle" fill="#991b1b" font-weight="bold">Redis Cache</text>



&#x20;           <rect x="150" y="690" width="180" height="45" rx="4" fill="#fff7ed" stroke="#ea580c" stroke-width="1"/>

&#x20;           <text x="240" y="717" font-size="12" text-anchor="middle" fill="#c2410c" font-weight="bold">Knowledge Base (SOPs)</text>



&#x20;           <rect x="345" y="690" width="190" height="45" rx="4" fill="#faf5ff" stroke="#9333ea" stroke-width="1.5"/>

&#x20;           <text x="440" y="710" font-size="11" text-anchor="middle" fill="#6b21a8" font-weight="bold">Vector Database</text>

&#x20;           <text x="440" y="725" font-size="10" text-anchor="middle" fill="#6b21a8">(Future RAG Production)</text>



&#x20;           <rect x="560" y="610" width="330" height="140" rx="6" fill="#fbfbfe" stroke="#cbd5e1" stroke-width="1.5"/>

&#x20;           <text x="580" y="640" font-size="14" font-weight="bold" fill="#475569">MONITORING LAYER</text>

&#x20;           <rect x="580" y="670" width="90" height="50" rx="4" fill="#fff7ed" stroke="#ea580c" stroke-width="1"/>

&#x20;           <text x="625" y="700" font-size="12" text-anchor="middle" fill="#c2410c">Prometheus</text>

&#x20;           <rect x="680" y="670" width="90" height="50" rx="4" fill="#f0fdfa" stroke="#14b8a6" stroke-width="1"/>

&#x20;           <text x="725" y="700" font-size="12" text-anchor="middle" fill="#115e59">Grafana</text>

&#x20;           <rect x="780" y="670" width="95" height="50" rx="4" fill="#f8fafc" stroke="#64748b" stroke-width="1"/>

&#x20;           <text x="827" y="700" font-size="11" text-anchor="middle" fill="#334155">Central Logs</text>

&#x20;       </svg>

&#x20;   </div>



&#x20;   <div class="legend">

&#x20;       <div class="legend-item"><div class="legend-color" style="background: #eff6ff; border:1px solid #3b82f6;"></div>Presentation</div>

&#x20;       <div class="legend-item"><div class="legend-color" style="background: #faf5ff; border:1px solid #a855f7;"></div>AI Core (LangGraph)</div>

&#x20;       <div class="legend-item"><div class="legend-color" style="background: #032d26;"></div>ServiceNow Standard Ecosystem</div>

&#x20;   </div>



&#x20;   <h2>Architecture 2: LangGraph Core Cognitive Execution Flow</h2>

&#x20;   <div class="diagram-wrapper">

&#x20;       <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" width="100%">

&#x20;           <defs>

&#x20;               <marker id="blackarrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">

&#x20;                   <path d="M 0 1 L 10 5 L 0 9 z" fill="#1e293b"/>

&#x20;               </marker>

&#x20;           </defs>



&#x20;           <rect x="20" y="20" width="240" height="560" rx="8" fill="#f8fafc" stroke="#e2e8f0" stroke-width="2"/>

&#x20;           <text x="140" y="45" font-size="14" font-weight="bold" text-anchor="middle" fill="#475569">1. INGEST \& RECALL</text>

&#x20;           

&#x20;           <rect x="40" y="70" width="200" height="50" rx="4" fill="#0078d4" stroke="#005a9e" stroke-width="1"/>

&#x20;           <text x="140" y="100" font-size="12" font-weight="bold" text-anchor="middle" fill="#ffffff">User Query Received</text>

&#x20;           

&#x20;           <path d="M 140 120 L 140 150" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>

&#x20;           

&#x20;           <rect x="40" y="150" width="200" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="1.5"/>

&#x20;           <text x="140" y="175" font-size="12" font-weight="bold" text-anchor="middle" fill="#6b21a8">Intent Agent</text>

&#x20;           <text x="140" y="195" font-size="11" text-anchor="middle" fill="#7e22ce">Classifies IT Request category</text>



&#x20;           <path d="M 140 210 L 140 240" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="40" y="240" width="200" height="50" rx="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1"/>

&#x20;           <text x="140" y="270" font-size="12" text-anchor="middle" fill="#334155">Fetch Conversation Memory</text>



&#x20;           <path d="M 140 290 L 140 320" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="40" y="320" width="200" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="1.5"/>

&#x20;           <text x="140" y="345" font-size="12" font-weight="bold" text-anchor="middle" fill="#6b21a8">Knowledge Agent</text>

&#x20;           <text x="140" y="365" font-size="11" text-anchor="middle" fill="#7e22ce">Retrieves SOPs \& KB vectors</text>



&#x20;           <path d="M 260 350 L 320 100" stroke="#1e293b" stroke-width="1.5" stroke-dasharray="4,4" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="320" y="20" width="260" height="560" rx="8" fill="#f5f3ff" stroke="#e9d5ff" stroke-width="2"/>

&#x20;           <text x="450" y="45" font-size="14" font-weight="bold" text-anchor="middle" fill="#6b21a8">2. DIAGNOSTIC REASONING</text>



&#x20;           <rect x="350" y="70" width="200" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="1"/>

&#x20;           <text x="450" y="95" font-size="12" font-weight="bold" text-anchor="middle" fill="#6b21a8">Diagnostic Interviewer</text>

&#x20;           <text x="450" y="115" font-size="11" text-anchor="middle" fill="#4c1d95">Asks clarifying queries to user</text>



&#x20;           <path d="M 450 130 L 450 160" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="350" y="160" width="200" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="1"/>

&#x20;           <text x="450" y="185" font-size="12" font-weight="bold" text-anchor="middle" fill="#6b21a8">Multi-Step Planner</text>

&#x20;           <text x="450" y="205" font-size="11" text-anchor="middle" fill="#4c1d95">Determines diagnostics tool map</text>



&#x20;           <path d="M 450 220 L 450 250" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="350" y="250" width="200" height="50" rx="4" fill="#fffbeb" stroke="#f59e0b" stroke-width="1.5"/>

&#x20;           <text x="450" y="272" font-size="11" font-weight="bold" text-anchor="middle" fill="#78350f">Tool Execution \& Evidence</text>

&#x20;           <text x="450" y="288" font-size="10" text-anchor="middle" fill="#78350f">(Pings AD, VPN endpoints, Network)</text>



&#x20;           <path d="M 450 300 L 450 330" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="350" y="330" width="200" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="1"/>

&#x20;           <text x="450" y="355" font-size="12" font-weight="bold" text-anchor="middle" fill="#6b21a8">Hypothesis Tracker</text>

&#x20;           <text x="450" y="375" font-size="11" text-anchor="middle" fill="#4c1d95">Tracks failures / root causes</text>



&#x20;           <path d="M 450 390 L 450 420" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="350" y="420" width="200" height="60" rx="4" fill="#edf2f7" stroke="#4a5568" stroke-width="1.5"/>

&#x20;           <text x="450" y="445" font-size="11" font-weight="bold" text-anchor="middle" fill="#2d3748">RCA Summary Engine</text>

&#x20;           <text x="450" y="465" font-size="11" text-anchor="middle" fill="#2d3748">Outputs Score \& Eng. Report</text>



&#x20;           <path d="M 580 450 L 620 100" stroke="#1e293b" stroke-width="1.5" stroke-dasharray="4,4" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="620" y="20" width="260" height="560" rx="8" fill="#f0fdf4" stroke="#bbf7d0" stroke-width="2"/>

&#x20;           <text x="750" y="45" font-size="14" font-weight="bold" text-anchor="middle" fill="#166534">3. DECISION \& ACTIONS</text>



&#x20;           <rect x="640" y="70" width="220" height="60" rx="4" fill="#ffffff" stroke="#a855f7" stroke-width="2"/>

&#x20;           <text x="750" y="95" font-size="13" font-weight="bold" text-anchor="middle" fill="#6b21a8">Decision Engine</text>

&#x20;           <text x="750" y="115" font-size="11" text-anchor="middle" fill="#4c1d95">Calculates Policy Validation</text>



&#x20;           <path d="M 750 150 L 830 190 L 750 230 L 670 190 Z" fill="#fffbeb" stroke="#d97706" stroke-width="1.5"/>

&#x20;           <text x="750" y="195" font-size="11" font-weight="bold" text-anchor="middle" fill="#78350f">Confidence</text>

&#x20;           <text x="750" y="210" font-size="11" font-weight="bold" text-anchor="middle" fill="#78350f">High?</text>



&#x20;           <path d="M 670 190 L 650 190 L 650 280 L 670 280" stroke="#166534" stroke-width="1.5" marker-end="url(#blackarrow)"/>

&#x20;           <text x="635" y="230" font-size="10" fill="#166534" font-weight="bold">YES</text>



&#x20;           <rect x="670" y="250" width="190" height="60" rx="4" fill="#ffffff" stroke="#166534" stroke-width="1.5"/>

&#x20;           <text x="765" y="275" font-size="12" font-weight="bold" text-anchor="middle" fill="#14532d">Execute Auto-Remediation</text>

&#x20;           <text x="765" y="295" font-size="10" text-anchor="middle" fill="#14532d">(Triggers APIs / Notifies Team)</text>



&#x20;           <path d="M 750 230 L 750 350" stroke="#b91c1c" stroke-width="1.5" marker-end="url(#blackarrow)"/>

&#x20;           <text x="760" y="245" font-size="10" fill="#b91c1c" font-weight="bold">NO / Policy Limit</text>



&#x20;           <rect x="650" y="350" width="210" height="60" rx="4" fill="#032d26" stroke="#011915" stroke-width="1"/>

&#x20;           <text x="755" y="375" font-size="12" font-weight="bold" text-anchor="middle" fill="#ffffff">Create ServiceNow Ticket</text>

&#x20;           <text x="755" y="395" font-size="10" text-anchor="middle" fill="#a3b899">Predicts priority \& assigns group</text>



&#x20;           <path d="M 755 410 L 755 440" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="660" y="440" width="190" height="40" rx="4" fill="#ffffff" stroke="#475569" stroke-width="1"/>

&#x20;           <text x="755" y="464" font-size="11" text-anchor="middle" fill="#334155">SLA Core Monitoring Engine</text>



&#x20;           <path d="M 755 480 L 755 510" stroke="#1e293b" stroke-width="1.5" marker-end="url(#blackarrow)"/>



&#x20;           <rect x="660" y="510" width="190" height="40" rx="4" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1"/>

&#x20;           <text x="755" y="534" font-size="12" font-weight="bold" text-anchor="middle" fill="#475569">Audit Log \& Exit</text>

&#x20;       </svg>

&#x20;   </div>

</div>



</body>

</html>

