"""Numbers for the bot's admin menu, the daily report and the admin Mini App - computed by the dashboard's own
queries (app.web.admin.analytics), so the bot and the dashboard never disagree."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Feedback, SurveyCampaign
from app.runtime import tunnel_status, webapp_url
from app.services.survey import active_campaign
from app.web.admin import analytics as an

TASHKENT = ZoneInfo("Asia/Tashkent")
TUNNEL_STALE = 300  # seconds: older than this, the watchdog's "ok" isn't trusted


def site_state() -> dict:
    """The public address and whether it works, as the server (app.server) last checked it."""
    url = webapp_url()
    st = tunnel_status()
    ago = int(datetime.now(timezone.utc).timestamp()) - st["at"] if st["at"] else None
    state = st["state"] if url else "none"
    if state == "ok" and (ago is None or ago > TUNNEL_STALE):
        state = "unknown"
    return {"url": url, "state": state, "ago_min": ago // 60 if ago is not None else None}


async def latest_campaign(session: AsyncSession) -> SurveyCampaign | None:
    """The open survey, else the last one that has started."""
    if open_c := await active_campaign(session):
        return open_c
    return await session.scalar(select(SurveyCampaign).where(SurveyCampaign.opens_at <= datetime.now(timezone.utc))
                                .order_by(SurveyCampaign.opens_at.desc()).limit(1))


async def snapshot(session: AsyncSession, detail: bool = False) -> dict:
    campaign = await latest_campaign(session)
    now = datetime.now(TASHKENT)
    out = {
        "campaign": None,
        "students": await an.student_total(session),
        "in_bot": await an.in_bot(session),
        "site": site_state(),
    }
    if campaign is None:
        return out
    is_open = campaign.opens_at <= datetime.now(timezone.utc) < campaign.closes_at
    k = await an.kpis(session, campaign.id)
    groups = await an.group_table(session, campaign.id)
    today = await session.scalar(select(func.count(Feedback.id)).where(
        Feedback.campaign_id == campaign.id, an.LOCAL_DAY == now.date()))
    out["campaign"] = {"id": campaign.id, "title": campaign.title, "open": is_open,
                       "closes": campaign.closes_at.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M"),
                       "days_left": (campaign.closes_at.astimezone(TASHKENT).date() - now.date()).days}
    out |= {"participants": k["participants"], "participation_pct": k["participation_pct"],
            "evaluations": k["evaluations"], "comments": k["comments"], "today": today,
            "overall": k["overall"], "teaching": k["teaching"], "fairness": k["fairness"],
            "professionalism": k["professionalism"], "completed": sum(g["completed"] for g in groups)}
    if detail:
        out["courses"] = [c for c in an.course_summary(groups) if c["students"]]
        out["low_groups"] = sorted((g for g in groups if g["students"]),
                                   key=lambda g: (g["participation_pct"], g["name"]))[:5]
        out["daily"] = (await an.daily_submissions(session, campaign.id))[-7:]
    return out
