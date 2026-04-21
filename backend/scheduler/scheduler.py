"""
APScheduler setup. Three jobs:

1. check_followups  — every hour: process due follow-ups
2. send_approved    — every 60s: send emails approved by copilot users
3. reset_daily      — midnight: set today's warm-up limit
"""
from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import logging

from backend import db
from backend.pipeline import email_writer, sender, followup
from backend.scheduler.warmup import update_daily_limit
from backend.services import imap_poller

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()


async def check_followups() -> None:
    """Process all due follow-ups."""
    due = await db.get_due_followups()

    for fu in due:
        prospect = await db.get_prospect(fu["prospect_id"])
        if not prospect or not followup.should_followup(prospect):
            reason = "no prospect" if not prospect else f"status={prospect.get('status')}"
            logger.info("Cancelling follow-up %s for prospect %s (%s)",
                        fu["id"], fu["prospect_id"], reason)
            await db.update_followup(fu["id"], "cancelled")
            await db.log_action("followup_cancelled", fu["campaign_id"],
                                fu["prospect_id"], detail={"reason": reason})
            continue

        if not await sender.can_send():
            break  # Hit daily limit — rest will be picked up next hour

        # Find the original email
        campaign_emails = await db.list_emails(fu["campaign_id"])
        original = None
        for e in campaign_emails:
            if e["prospect_id"] == fu["prospect_id"] and e["email_type"] == "initial":
                original = e
                break

        if not original:
            await db.update_followup(fu["id"], "cancelled")
            continue

        # Generate follow-up email
        fu_data = await email_writer.write_followup_email(
            original, prospect, fu["followup_number"]
        )
        if not fu_data:
            logger.warning("email_writer returned nothing for follow-up %s — cancelling", fu["id"])
            await db.update_followup(fu["id"], "cancelled")
            await db.log_action("followup_cancelled", fu["campaign_id"],
                                fu["prospect_id"], detail={"reason": "email_writer_returned_none"})
            continue

        # Create the follow-up email record
        email_type = f"followup_{fu['followup_number']}"
        email_record = await db.create_email({
            "prospect_id": prospect["id"],
            "campaign_id": fu["campaign_id"],
            "email_type": email_type,
            "subject": fu_data["subject"],
            "body_html": fu_data["body_html"],
            "body_text": fu_data["body_text"],
            "personalisation_points": fu_data["personalisation_points"],
            "status": "approved",
        })

        # Check campaign autonomy
        campaign = await db.get_campaign(fu["campaign_id"])
        if campaign and campaign["autonomy"] == "copilot":
            await db.update_email(email_record["id"], {"status": "pending_approval"})
            await db.log_action("followup_pending_approval", fu["campaign_id"],
                                prospect["id"], email_record["id"])
            await db.update_followup(fu["id"], "sent")  # Mark schedule as processed
            continue

        # Send if not dry run
        if campaign and not campaign.get("dry_run"):
            result = await sender.send_email(email_record, prospect)
            if result["success"] and fu["followup_number"] < 2:
                # Schedule next follow-up
                await followup.schedule_followup(
                    email_record["id"], prospect["id"],
                    fu["campaign_id"], followup_number=fu["followup_number"] + 1,
                )
                await sender.spacing_delay()

        await db.update_followup(fu["id"], "sent")


async def send_approved_emails() -> None:
    """Send emails that have been approved by copilot users."""
    approved = await db.list_emails_by_status("approved")

    for email_record in approved:
        if not await sender.can_send():
            break

        prospect = await db.get_prospect(email_record["prospect_id"])
        if not prospect:
            continue

        campaign = await db.get_campaign(email_record["campaign_id"])
        if campaign and campaign.get("dry_run"):
            await db.log_action("dry_run_skip_send", email_record["campaign_id"],
                                prospect["id"], email_record["id"])
            continue

        result = await sender.send_email(email_record, prospect)
        if result["success"] and email_record["email_type"] == "initial":
            await followup.schedule_followup(
                email_record["id"], prospect["id"],
                email_record["campaign_id"], followup_number=1,
            )

        await sender.spacing_delay()


async def reset_daily_counter() -> None:
    """Reset the daily send counter and calculate today's warm-up limit."""
    limit = await update_daily_limit()
    await db.log_action("daily_limit_set", detail={"limit": limit})


async def poll_replies() -> None:
    """Poll inbox for replies to ColdPilot emails. Runs every 5 minutes."""
    try:
        found = await imap_poller.poll_for_replies()
        if found:
            logger.info("Reply poll: %d new replies detected", found)
    except Exception as exc:
        logger.error("Reply poll job failed: %s", exc)


def start_scheduler() -> None:
    """Register all jobs and start the scheduler."""
    scheduler.add_job(
        check_followups,
        IntervalTrigger(hours=1),
        id="check_followups",
        replace_existing=True,
    )
    scheduler.add_job(
        send_approved_emails,
        IntervalTrigger(seconds=60),
        id="send_approved",
        replace_existing=True,
    )
    scheduler.add_job(
        poll_replies,
        IntervalTrigger(minutes=5),
        id="poll_replies",
        replace_existing=True,
    )
    scheduler.add_job(
        reset_daily_counter,
        CronTrigger(hour=0, minute=0),
        id="reset_daily",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
