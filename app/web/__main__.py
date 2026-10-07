"""Run the web server (survey + admin dashboard):  python -m app.web"""
import uvicorn

from app.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    print(f"🌐 Dashboard: http://{s.web_host}:{s.web_port}/admin")
    uvicorn.run("app.web.main:app", host=s.web_host, port=s.web_port, proxy_headers=True, forwarded_allow_ips="*")
