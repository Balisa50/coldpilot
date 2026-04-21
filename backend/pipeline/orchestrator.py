"""
Pipeline orchestrator: runs all stages in sequence for each prospect,
handles the autonomy gate, concurrency, and SSE event publishing.

This is the brain of ColdPilot.
"""
from __future__ import annotations

import asyncio
import json

from backend import db, event_bus
from backend.pipeline import contact_finder, researcher, email_writer, sender, followup


MAX_CONCURRENT = 5
BOUNCE_RATE_THRESHOLD = 0.10  # Pause campaign when > 10% of sends bounce
BOUNCE_RATE_MIN_SAMPLE = 5    # Only enforce after this many sends


async def _publish(campaign_id: str, event_type: str, data: dict) -> None:
    """Publish an SSE event for the dashboard."""
    await event_bus.publish(campaign_id, {"event": event_type, **data})


async def _check_and_pause_on_bounce_rate(campaign_id: str) -> None:
    """Auto-pause a campaign whose bounce rate exceeds the threshold.

    Called after every bounce. Only evaluates once a minimum sample is available
    so a single early bounce doesn't kill the campaign prematurely.
    """
    emails = await db.list_emails(campaign_id)
    delivered = [e for e in emails if e["status"] in ("sent", "bounced", "replied")]
    bounced = [e for e in emails if e["status"] == "bounced"]
    if len(delivered) < BOUNCE_RATE_MIN_SAMPLE:
        return
    rate = len(bounced) / len(delivered)
    if rate > BOUNCE_RATE_THRESHOLD:
        await db.update_campaign(campaign_id, {"status": "paused"})
        await db.log_action(
            "campaign_auto_paused",
            campaign_id=campaign_id,
            detail={
                "reason": "bounce_rate_exceeded",
                "bounce_rate_pct": round(rate * 100, 1),
                "threshold_pct": round(BOUNCE_RATE_THRESHOLD * 100, 1),
            },
        )
        await _publish(campaign_id, "campaign_auto_paused", {
            "reason": f"Bounce rate {round(rate * 100, 1)}% exceeded {round(BOUNCE_RATE_THRESHOLD * 100)}% threshold. Campaign paused to protect sender reputation.",
        })


async def process_prospect(
    prospect: dict,
    campaign: dict,
    semaphore: asyncio.Semaphore,
) -> None:
    """Run the full pipeline for one prospect."""
    cid = campaign["id"]
    pid = prospect["id"]

    async with semaphore:
        try:
            # Stage 1: Contact Finding — SKIP if prospect already has email (manual entry)
            if prospect.get("contact_email"):
                # User already provided contact info — skip straight to research
                await db.update_prospect(pid, {"status": "contact_found"})
                await db.log_action("contact_provided", cid, pid,
                                    detail={"email": prospect["contact_email"],
                                            "source": "manual"})
                await _publish(cid, "contact_found", {
                    "prospect_id": pid,
                    "contact_email": prospect["contact_email"],
                    "contact_name": prospect.get("contact_name", ""),
                    "contact_role": prospect.get("contact_role", ""),
                    "company_name": prospect.get("company_name", ""),
                    "source": "manual",
                })
            else:
                await db.update_prospect(pid, {"status": "researching"})
                await _publish(cid, "stage_start", {"prospect_id": pid, "stage": "contact_finding"})

                contact = await contact_finder.find_contact(prospect, campaign)

                if not contact or not contact.get("contact_email"):
                    await db.update_prospect(pid, {"status": "failed"})
                    await db.log_action("contact_not_found", cid, pid,
                                        detail={"company": prospect["company_name"]})
                    await _publish(cid, "contact_not_found", {"prospect_id": pid})
                    return

                # Gate: never send to unverified pattern-guessed emails.
                # Pattern guessing is just first.last@domain with no verification.
                # Sending to these wrecks sender reputation and risks CAN-SPAM violations.
                if contact.get("email_source") == "pattern_guess" and not contact.get("email_verified"):
                    await db.update_prospect(pid, {"status": "failed"})
                    await db.log_action("skipped_unverified_guess", cid, pid,
                                        detail={"email": contact["contact_email"],
                                                "reason": "Pattern-guessed address — unverifiable"})
                    await _publish(cid, "contact_skipped", {
                        "prospect_id": pid,
                        "reason": "Could not find a verified email. Add one manually to include this contact.",
                    })
                    return

                await db.update_prospect(pid, {
                    "contact_name": contact.get("contact_name", prospect.get("contact_name")),
                    "contact_email": contact["contact_email"],
                    "contact_role": contact.get("contact_role", ""),
                    "email_source": contact.get("email_source", "hunter"),
                    "email_verified": contact.get("email_verified", 0),
                    "status": "contact_found",
                })
                await db.log_action("contact_found", cid, pid,
                                    detail={"email": contact["contact_email"],
                                            "source": contact.get("email_source")})
                await _publish(cid, "contact_found", {
                    "prospect_id": pid,
                    "contact_email": contact["contact_email"],
                    "contact_name": contact.get("contact_name", ""),
                    "contact_role": contact.get("contact_role", ""),
                    "company_name": prospect.get("company_name", ""),
                })

            # Refresh prospect after update
            prospect = await db.get_prospect(pid)

            # Global suppression: never email opted-out contacts or recent contacts
            email_addr = prospect.get("contact_email", "")
            if email_addr:
                if await db.is_opted_out(email_addr):
                    await db.update_prospect(pid, {"status": "opted_out"})
                    await db.log_action("suppressed_opted_out", cid, pid,
                                        detail={"email": email_addr})
                    await _publish(cid, "contact_skipped", {
                        "prospect_id": pid,
                        "reason": "This address previously unsubscribed — not contacting again.",
                    })
                    return
                # Skip cooldown check for dry runs — they don't actually send,
                # so repeatedly testing with the same address should work fine.
                if not campaign.get("dry_run") and await db.was_recently_contacted(email_addr, within_days=30):
                    await db.update_prospect(pid, {"status": "failed"})
                    await db.log_action("suppressed_recently_contacted", cid, pid,
                                        detail={"email": email_addr})
                    await _publish(cid, "contact_skipped", {
                        "prospect_id": pid,
                        "reason": "Already emailed this address in the last 30 days.",
                    })
                    return

            # Stage 2: Research
            await _publish(cid, "stage_start", {"prospect_id": pid, "stage": "research"})

            notes = await researcher.research(
                prospect["company_name"],
                prospect.get("company_domain"),
                context=campaign.get("desired_role", "") if campaign["mode"] == "seeker" else "",
            )
            await db.update_prospect(pid, {"research_notes": notes})
            await db.log_action("research_complete", cid, pid,
                                detail={"summary": notes.get("summary", "")[:200]})
            await _publish(cid, "research_complete", {
                "prospect_id": pid,
                "summary": notes.get("summary", "")[:200],
            })

            # Stage 3: Email Writing
            await _publish(cid, "stage_start", {"prospect_id": pid, "stage": "email_writing"})

            email_data = await email_writer.write_initial_email(campaign, prospect, notes)
            if not email_data or email_data.get("__error__"):
                err = (email_data or {}).get("__error__", "Unknown error")
                await db.update_prospect(pid, {"status": "failed"})
                await db.log_action("email_write_failed", cid, pid,
                                    detail={"error": err})
                await _publish(cid, "email_write_failed", {
                    "prospect_id": pid,
                    "error": err,
                })
                return

            email_record = await db.create_email({
                "prospect_id": pid,
                "campaign_id": cid,
                "email_type": "initial",
                "subject": email_data["subject"],
                "body_html": email_data["body_html"],
                "body_text": email_data["body_text"],
                "personalisation_points": email_data["personalisation_points"],
                "status": "draft",
            })
            await db.update_prospect(pid, {"status": "email_drafted"})
            await db.log_action("email_drafted", cid, pid, email_record["id"],
                                detail={"subject": email_data["subject"]})
            await _publish(cid, "email_drafted", {
                "prospect_id": pid,
                "email_id": email_record["id"],
                "subject": email_data["subject"],
            })

            # Stage 4: Autonomy Gate
            if campaign["autonomy"] == "copilot":
                await db.update_email(email_record["id"], {"status": "pending_approval"})
                await db.log_action("email_pending_approval", cid, pid, email_record["id"])
                await _publish(cid, "email_pending_approval", {
                    "prospect_id": pid,
                    "email_id": email_record["id"],
                })
                return  # Stop here — user must approve

            # Supervised / Full Auto: auto-approve
            await db.update_email(email_record["id"], {"status": "approved"})

            # Stage 5: Sending
            if campaign.get("dry_run"):
                await db.log_action("dry_run_skip_send", cid, pid, email_record["id"])
                await _publish(cid, "dry_run_skip_send", {
                    "prospect_id": pid,
                    "email_id": email_record["id"],
                })
            else:
                await _publish(cid, "stage_start", {"prospect_id": pid, "stage": "sending"})

                if not await sender.can_send():
                    await db.log_action("daily_limit_reached", cid, pid, email_record["id"])
                    await _publish(cid, "daily_limit_reached", {"prospect_id": pid})
                    return  # Scheduler will pick up approved emails later

                send_result = await sender.send_email(email_record, prospect)

                if send_result["success"]:
                    await _publish(cid, "email_sent", {
                        "prospect_id": pid,
                        "email_id": email_record["id"],
                        "to": prospect["contact_email"],
                    })

                    # Stage 6: Schedule follow-up
                    await followup.schedule_followup(
                        email_record["id"], pid, cid, followup_number=1
                    )
                    await _publish(cid, "followup_scheduled", {
                        "prospect_id": pid,
                        "followup_number": 1,
                    })

                    # Spacing between sends
                    await sender.spacing_delay()
                else:
                    if send_result.get("bounce"):
                        await _check_and_pause_on_bounce_rate(cid)
                    await _publish(cid, "send_failed", {
                        "prospect_id": pid,
                        "error": send_result.get("error", ""),
                        "bounce": send_result.get("bounce", False),
                    })

        except Exception as e:
            await db.update_prospect(pid, {"status": "failed"})
            await db.log_action("pipeline_error", cid, pid,
                                detail={"error": str(e)})
            await _publish(cid, "pipeline_error", {
                "prospect_id": pid,
                "error": str(e),
            })


async def run_campaign(campaign_id: str) -> None:
    """
    Run the full pipeline for a campaign. Processes up to MAX_CONCURRENT
    prospects at a time.
    """
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        return

    await db.update_campaign(campaign_id, {"status": "active"})
    await db.log_action("campaign_started", campaign_id)
    await _publish(campaign_id, "campaign_started", {"campaign_id": campaign_id})

    prospects = await db.list_prospects(campaign_id)
    # Include both "pending" and "contact_found" (manually added with email)
    pending = [p for p in prospects if p["status"] in ("pending", "contact_found")]

    if not pending:
        await db.log_action("campaign_no_prospects", campaign_id)
        await _publish(campaign_id, "campaign_no_prospects", {})
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # Process all pending prospects concurrently (bounded by semaphore)
    tasks = [
        process_prospect(prospect, campaign, semaphore)
        for prospect in pending
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Check if campaign is done (all prospects processed)
    campaign = await db.get_campaign(campaign_id)
    if campaign and campaign["status"] == "active":
        remaining = await db.list_prospects(campaign_id)
        still_pending = [p for p in remaining if p["status"] == "pending"]
        if not still_pending:
            # Don't mark as completed if copilot mode has pending approvals
            if campaign["autonomy"] != "copilot":
                await db.update_campaign(campaign_id, {"status": "completed"})
                await db.log_action("campaign_completed", campaign_id)
                await _publish(campaign_id, "campaign_completed", {})
