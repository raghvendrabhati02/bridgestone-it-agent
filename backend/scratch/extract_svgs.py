import re
import os

ARTIFACTS_DIR = r"C:\Users\raghvendra-bhati\.gemini\antigravity-ide\brain\ad2d4297-fa78-4591-b729-509c43bc1132"
SYSTEM_ARCH_PATH = r"c:\Projects\bridgestone-it-agent\docs\system-architecture.md"

def extract_svgs():
    if not os.path.exists(SYSTEM_ARCH_PATH):
        print(f"Error: {SYSTEM_ARCH_PATH} does not exist.")
        return
        
    with open(SYSTEM_ARCH_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Find all <svg ... </svg> blocks (including multiline, non-greedy)
    svgs = re.findall(r"(<svg.*?</svg>)", content, re.DOTALL)
    print(f"Found {len(svgs)} SVG elements.")
    
    if len(svgs) >= 1:
        # Save first SVG as enterprise_architecture.svg
        arch_svg_path = os.path.join(ARTIFACTS_DIR, "enterprise_architecture.svg")
        # Clean up any HTML entities like &#x20; if they exist
        svg_content = svgs[0].replace("&#x20;", " ")
        with open(arch_svg_path, "w", encoding="utf-8") as out:
            out.write(svg_content)
        print(f"Saved: {arch_svg_path}")
        
    if len(svgs) >= 2:
        # Save second SVG as cognitive_flow.svg
        flow_svg_path = os.path.join(ARTIFACTS_DIR, "cognitive_flow.svg")
        svg_content = svgs[1].replace("&#x20;", " ")
        with open(flow_svg_path, "w", encoding="utf-8") as out:
            out.write(svg_content)
        print(f"Saved: {flow_svg_path}")

if __name__ == "__main__":
    extract_svgs()
