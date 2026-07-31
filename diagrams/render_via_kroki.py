import os
import requests

DIAGRAMS_DIR = r"C:\Projects\bridgestone-it-agent\diagrams"

def render_all():
    print("Rendering Mermaid diagrams using Kroki rendering service...")
    rendered = 0
    for file in os.listdir(DIAGRAMS_DIR):
        if file.endswith(".mmd"):
            mmd_path = os.path.join(DIAGRAMS_DIR, file)
            png_name = file.replace(".mmd", ".png")
            png_path = os.path.join(DIAGRAMS_DIR, png_name)

            with open(mmd_path, "r", encoding="utf-8") as f:
                mmd_source = f.read()

            # Prepend dark theme directive to mermaid diagram if not present
            if "%%{init:" not in mmd_source:
                theme_init = "%%{init: {'theme': 'dark', 'themeVariables': {'darkMode': true, 'background': '#0b0f19', 'primaryColor': '#1e293b', 'primaryTextColor': '#f8fafc', 'primaryBorderColor': '#38bdf8', 'lineColor': '#38bdf8', 'secondaryColor': '#0f172a', 'tertiaryColor': '#1e1e2e', 'fontFamily': 'Segoe UI, Calibri, sans-serif'}}}%%\n"
                mmd_source = theme_init + mmd_source

            resp = requests.post("https://kroki.io/mermaid/png", json={"diagram_source": mmd_source})
            if resp.status_code == 200:
                with open(png_path, "wb") as pf:
                    pf.write(resp.content)
                print(f"  [OK] Rendered {png_name} ({len(resp.content):,} bytes)")
                rendered += 1
            else:
                print(f"  [FAIL] Failed rendering {file}: HTTP {resp.status_code} - {resp.text}")

    print(f"\nCompleted: {rendered} diagrams rendered to PNG successfully.")

if __name__ == "__main__":
    render_all()
