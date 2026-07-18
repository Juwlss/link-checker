import sys
import asyncio
import httpx
from bs4 import BeautifulSoup
import pandas as pd
import gradio as gr
from fastapi import FastAPI

# Force text safety encoding
sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def fetch_and_check(client, page, links_to_find, progress_tracker):
    try:
        response = await client.get(page, headers=HEADERS, timeout=10.0, follow_redirects=True)
        if response.status_code != 200:
            result = {"Page URL": page, "Status": f"ERROR: HTTP {response.status_code}"}
        else:
            soup = BeautifulSoup(response.text, 'html.parser')
            links = [a['href'].strip().lower() for a in soup.find_all('a', href=True)]
            
            found = False
            for target in links_to_find:
                clean_target = target.lower().replace("https://", "").replace("http://", "").strip("/")
                if any(clean_target in link for link in links):
                    found = True
                    break
            result = {"Page URL": page, "Status": "FOUND" if found else "NOT FOUND"}
    except httpx.RequestError:
        result = {"Page URL": page, "Status": "ERROR: Can't access page"}
    except Exception:
        result = {"Page URL": page, "Status": "ERROR: Processing failed"}
    
    progress_tracker.update_progress(page)
    return result

class ProgressTracker:
    def __init__(self, total, progress_instance):
        self.total = total
        self.current = 0
        self.progress = progress_instance

    def update_progress(self, current_url):
        self.current += 1
        self.progress(self.current / self.total, desc=f"Processed {self.current}/{self.total} pages...")

def run_bulk_check(raw_target_pages, raw_links_to_find, prg=gr.Progress()):
    target_pages = [line.strip() for line in raw_target_pages.split("\n") if line.strip()]
    links_to_find = [line.strip() for line in raw_links_to_find.split("\n") if line.strip()]
    
    if not target_pages or not links_to_find:
        return "⚠️ Inputs missing.", None, None

    prg(0, desc="Initializing...")
    tracker = ProgressTracker(len(target_pages), prg)

    async def main():
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
        async with httpx.AsyncClient(limits=limits) as client:
            tasks = [fetch_and_check(client, page, links_to_find, tracker) for page in target_pages]
            return await asyncio.gather(*tasks)

    results = asyncio.run(main())
    output_file = "link_check_report.csv"
    pd.DataFrame(results).to_csv(output_file, index=False)
    return "🚀 Scan complete!", pd.DataFrame(results), output_file

# Create the visual page
with gr.Blocks(title="Bulk Link Checker") as demo:
    gr.Markdown("# ⚡ Permanent Bulk Link Checker UI")
    with gr.Row():
        with gr.Column():
            input_pages = gr.Textbox(label="1. Paste Webpages to Scan", lines=10)
            default_targets = """"""
            input_targets = gr.Textbox(label="2. Target Links to Find (EDITABLE)", value=default_targets, lines=5)
            submit_btn = gr.Button("🚀 Run Automated Check", variant="primary")
        with gr.Column():
            output_msg = gr.Textbox(label="System Status", interactive=False)
            output_file = gr.File(label="📥 Download Excel/CSV Report")
    output_table = gr.Dataframe(label="Live Results Preview", headers=["Page URL", "Status"])
    submit_btn.click(fn=run_bulk_check, inputs=[input_pages, input_targets], outputs=[output_msg, output_table, output_file])

# Integrate Gradio interface cleanly into a production web app
app = FastAPI()
app = gr.mount_gradio_app(app, demo, path="/")
