import httpx
from extractor.content import extract_markdown
from extractor.cleaner import clean_html

url = "https://docs.openclaw.ai/zh-CN/automation/troubleshooting"
html = httpx.get(url).text
cleaned = clean_html(html)
md_out = extract_markdown(cleaned, url=url, fallback_html=html)

print("Markdown size:", len(md_out))
print("First 200 chars:")
print(md_out[:200])
