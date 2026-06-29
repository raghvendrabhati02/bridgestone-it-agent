import os

ARTIFACTS_DIR = r"C:\Users\raghvendra-bhati\.gemini\antigravity-ide\brain\ad2d4297-fa78-4591-b729-509c43bc1132"
DRAWIO_PATH = os.path.join(ARTIFACTS_DIR, "enterprise_architecture.drawio")

xml_content = """<mxfile host="Electron" modified="2026-06-29T14:55:00.000Z" agent="5.0" version="20.0.0" type="device">
  <diagram id="bridgestone-architecture" name="Bridgestone Enterprise AI Service Desk">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1100" pageHeight="850" background="#FFFFFF">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        
        <!-- Layers swimlanes -->
        <mxCell id="layer-users" value="USERS (Employees, Managers, IT Administrators)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#f8fafc;strokeColor=#cbd5e1;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="50" width="1000" height="80" as="geometry" />
        </mxCell>
        <mxCell id="layer-presentation" value="PRESENTATION LAYER (Next.js Frontend)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#eff6ff;strokeColor=#bfdbfe;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="150" width="1000" height="90" as="geometry" />
        </mxCell>
        <mxCell id="layer-security" value="SECURITY &amp; GATEWAY (FastAPI security.py &amp; core/)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#fff1f2;strokeColor=#fecdd3;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="260" width="1000" height="90" as="geometry" />
        </mxCell>
        <mxCell id="layer-application" value="APPLICATION SERVICES (FastAPI app/services/)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#f0fdf4;strokeColor=#bbf7d0;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="370" width="1000" height="90" as="geometry" />
        </mxCell>
        <mxCell id="layer-ai" value="AI ORCHESTRATION LAYER (LangGraph Multi-Agent Grid)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#faf5ff;strokeColor=#e9d5ff;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="480" width="1000" height="100" as="geometry" />
        </mxCell>
        <mxCell id="layer-adapters" value="ENTERPRISE ADAPTER LAYER (app/adapters/)" style="swimlane;whiteSpace=wrap;html=1;fillColor=#f0fdfa;strokeColor=#ccfbf1;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="600" width="1000" height="90" as="geometry" />
        </mxCell>
        <mxCell id="layer-data" value="ENTERPRISE DATA &amp; STORAGE LAYER" style="swimlane;whiteSpace=wrap;html=1;fillColor=#f8fafc;strokeColor=#cbd5e1;startSize=40;" vertex="1" parent="1">
          <mxGeometry x="50" y="710" width="1000" height="100" as="geometry" />
        </mxCell>

        <!-- Components in USERS -->
        <mxCell id="user-employee" value="Bridgestone Employee" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#94a3b8;" vertex="1" parent="layer-users">
          <mxGeometry x="150" y="25" width="150" height="30" as="geometry" />
        </mxCell>
        <mxCell id="user-manager" value="Manager / Approver" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#94a3b8;" vertex="1" parent="layer-users">
          <mxGeometry x="400" y="25" width="150" height="30" as="geometry" />
        </mxCell>
        <mxCell id="user-admin" value="IT Administrator" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#94a3b8;" vertex="1" parent="layer-users">
          <mxGeometry x="650" y="25" width="150" height="30" as="geometry" />
        </mxCell>

        <!-- Components in PRESENTATION -->
        <mxCell id="pres-portal" value="Next.js Portal" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#3b82f6;" vertex="1" parent="layer-presentation">
          <mxGeometry x="150" y="25" width="130" height="40" as="geometry" />
        </mxCell>
        <mxCell id="pres-chat" value="Interactive Chat UI" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#3b82f6;" vertex="1" parent="layer-presentation">
          <mxGeometry x="350" y="25" width="130" height="40" as="geometry" />
        </mxCell>
        <mxCell id="pres-dashboard" value="Executive Dashboard" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#3b82f6;" vertex="1" parent="layer-presentation">
          <mxGeometry x="550" y="25" width="130" height="40" as="geometry" />
        </mxCell>

        <!-- Components in SECURITY -->
        <mxCell id="sec-jwt" value="JWT Auth Verification" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#f43f5e;" vertex="1" parent="layer-security">
          <mxGeometry x="150" y="25" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="sec-rbac" value="RBAC Policy Filter" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#f43f5e;" vertex="1" parent="layer-security">
          <mxGeometry x="400" y="25" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="sec-limits" value="Rate Limiter \&amp; Sanitizer" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#f43f5e;" vertex="1" parent="layer-security">
          <mxGeometry x="650" y="25" width="170" height="40" as="geometry" />
        </mxCell>

        <!-- Components in APPLICATION -->
        <mxCell id="app-conv" value="Conversation Svc" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#22c55e;" vertex="1" parent="layer-application">
          <mxGeometry x="100" y="25" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="app-ticket" value="Ticket Service" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#22c55e;" vertex="1" parent="layer-application">
          <mxGeometry x="250" y="25" width="110" height="40" as="geometry" />
        </mxCell>
        <mxCell id="app-sla" value="SLA Monitor Engine" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#22c55e;" vertex="1" parent="layer-application">
          <mxGeometry x="390" y="25" width="130" height="40" as="geometry" />
        </mxCell>
        <mxCell id="app-approval" value="Approval Workflows" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#22c55e;" vertex="1" parent="layer-application">
          <mxGeometry x="550" y="25" width="130" height="40" as="geometry" />
        </mxCell>
        <mxCell id="app-scheduler" value="Background Scheduler" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#22c55e;" vertex="1" parent="layer-application">
          <mxGeometry x="710" y="25" width="150" height="40" as="geometry" />
        </mxCell>

        <!-- Components in AI -->
        <mxCell id="ai-intent" value="Intent Agent" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a855f7;strokeWidth=2;" vertex="1" parent="layer-ai">
          <mxGeometry x="100" y="30" width="110" height="40" as="geometry" />
        </mxCell>
        <mxCell id="ai-knowledge" value="Knowledge Agent" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a855f7;" vertex="1" parent="layer-ai">
          <mxGeometry x="240" y="30" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="ai-planner" value="Planner Agent" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a855f7;" vertex="1" parent="layer-ai">
          <mxGeometry x="390" y="30" width="110" height="40" as="geometry" />
        </mxCell>
        <mxCell id="ai-diag" value="Diagnostic Agent" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a855f7;" vertex="1" parent="layer-ai">
          <mxGeometry x="530" y="30" width="120" height="40" as="geometry" />
        </mxCell>
        <mxCell id="ai-decision" value="Decision Router" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a855f7;" vertex="1" parent="layer-ai">
          <mxGeometry x="680" y="30" width="110" height="40" as="geometry" />
        </mxCell>

        <!-- Components in ADAPTERS -->
        <mxCell id="adapt-vpn" value="VPN / Net Adapter" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#14b8a6;" vertex="1" parent="layer-adapters">
          <mxGeometry x="100" y="25" width="130" height="40" as="geometry" />
        </mxCell>
        <mxCell id="adapt-ad" value="Active Directory Adapter" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#14b8a6;" vertex="1" parent="layer-adapters">
          <mxGeometry x="260" y="25" width="160" height="40" as="geometry" />
        </mxCell>
        <mxCell id="adapt-graph" value="Microsoft Graph Adapter" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#14b8a6;" vertex="1" parent="layer-adapters">
          <mxGeometry x="450" y="25" width="160" height="40" as="geometry" />
        </mxCell>
        <mxCell id="adapt-snow" value="ServiceNow Spoke API" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#032d26;strokeWidth=2;" vertex="1" parent="layer-adapters">
          <mxGeometry x="640" y="25" width="170" height="40" as="geometry" />
        </mxCell>

        <!-- Components in DATA -->
        <mxCell id="data-sqlite" value="SQLite DB (Dev Cache)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#94a3b8;strokeDasharray=3,3;" vertex="1" parent="layer-data">
          <mxGeometry x="100" y="30" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="data-postgres" value="PostgreSQL (Audits \&amp; SLA)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e0f2fe;strokeColor=#0288d1;" vertex="1" parent="layer-data">
          <mxGeometry x="280" y="30" width="180" height="40" as="geometry" />
        </mxCell>
        <mxCell id="data-redis" value="Redis Session Cache" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fef2f2;strokeColor=#dc2626;" vertex="1" parent="layer-data">
          <mxGeometry x="490" y="30" width="150" height="40" as="geometry" />
        </mxCell>
        <mxCell id="data-kb" value="Vector Store (KB SOPs)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fff7ed;strokeColor=#ea580c;" vertex="1" parent="layer-data">
          <mxGeometry x="670" y="30" width="170" height="40" as="geometry" />
        </mxCell>

        <!-- Flows (Edges) -->
        <mxCell id="edge1" value="HTTP Request" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-users" target="layer-presentation">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="edge2" value="Secure REST" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-presentation" target="layer-security">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="edge3" value="Validated Svc" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-security" target="layer-application">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="edge4" value="Orchestrate" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-application" target="layer-ai">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="edge5" value="Dispatch" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-ai" target="layer-adapters">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="edge6" value="Persist" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#4b5563;" edge="1" parent="1" source="layer-adapters" target="layer-data">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

with open(DRAWIO_PATH, "w", encoding="utf-8") as out:
    out.write(xml_content)
print(f"Created Draw.io file: {DRAWIO_PATH}")
