"""下载报告到本地"""
import requests, json, os

BASE = "http://127.0.0.1:5001/api"

# 列出所有报告
r = requests.get(f"{BASE}/report/list", timeout=10)
reports = r.json().get("data", [])
print(f"共 {len(reports)} 份报告", flush=True)

for rpt in reports:
    rid = rpt.get("report_id", "?")
    print(f"  {rid} | {rpt.get('status','?')} | {rpt.get('created_at','?')}", flush=True)

    # 下载完整报告
    r2 = requests.get(f"{BASE}/report/{rid}", timeout=10)
    data = r2.json().get("data", {})
    
    if data.get("status") == "completed":
        out_path = os.path.join(os.getcwd(), f"{rid}_report.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  已保存: {out_path}", flush=True)

        # 也导出为可读的 Markdown
        md_path = os.path.join(os.getcwd(), f"{rid}_report.md")
        outline = data.get("outline", {})
        sections = data.get("sections", {})
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# {outline.get('title', '报告')}\n\n")
            f.write(f"> {outline.get('summary', '')}\n\n")
            f.write(f"---\n\n")
            for k in sorted(sections.keys(), key=lambda x: int(x)):
                sec = sections[k]
                f.write(f"## {sec.get('title', f'第{k}章')}\n\n")
                f.write(f"{sec.get('content', '')}\n\n")
                findings = sec.get("key_findings", [])
                if findings:
                    f.write("**关键发现：**\n\n")
                    for fi in findings:
                        f.write(f"- {fi}\n")
                    f.write("\n")
                evidence = sec.get("evidence", [])
                if evidence:
                    f.write("**支撑证据：**\n\n")
                    for ev in evidence:
                        f.write(f"- {ev}\n")
                    f.write("\n")
                f.write("---\n\n")
        print(f"  已保存: {md_path}", flush=True)
