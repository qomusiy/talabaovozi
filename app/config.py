from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://feedback:feedback_dev_pw@127.0.0.1:5433/feedback"
    secret_key: str

    bot_token: str = ""
    # Shown to students: general questions / technical problems with the bot.
    support_contact: str = "@tridonus"
    tech_contact: str = "@qomusiy"
    # Specialty codes of Economics Faculty groups, as they appear in timetable group names ("25-16 IQT (ru)").
    faculty_group_codes: str = "IQT,BXA,TUR,STAT,FTO'IT,FTO'RT,BB,ATT"
    # Timetable: the university's EduPage site, and the faculty section its groups are listed under there.
    edupage_url: str = "https://tiiame.edupage.org"
    edupage_faculty: str = "Iqtisodiyot"
    # Public HTTPS URL of the survey web app (Telegram Mini App). Empty: the address of the tunnel (app.server) is used.
    webapp_url: str = ""
    # How app.server makes the public address: quick (changes after every restart), tailscale or cloudflare
    # (the same address forever - README › Fixed address).
    tunnel: str = "quick"
    cloudflare_tunnel_token: str = ""   # TUNNEL=cloudflare only
    # TUNNEL=tailscale: when the Tailscale address stops answering, students get a Cloudflare quick tunnel meanwhile.
    tunnel_backup: bool = True

    # Web server (survey + admin dashboard). 0.0.0.0: also reachable at this computer's Tailscale address, where
    # the dashboard opens for your own devices (README › Remote access; nothing else gets the dashboard).
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    # DEV ONLY: lets you open the survey in a normal browser on this computer: /survey?dev=<Telegram id>
    dev_mode: bool = False
    # Only serve /admin to requests addressed to localhost (so a public tunnel exposes the survey, not the dashboard).
    admin_local_only: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
