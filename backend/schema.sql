-- ColdPilot database schema

CREATE TABLE IF NOT EXISTS campaigns (
    id                  TEXT PRIMARY KEY,
    mode                TEXT NOT NULL CHECK(mode IN ('hunter', 'seeker')),
    autonomy            TEXT NOT NULL DEFAULT 'copilot'
                        CHECK(autonomy IN ('copilot', 'supervised', 'full_auto')),
    name                TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft', 'active', 'paused', 'completed')),
    dry_run             INTEGER NOT NULL DEFAULT 0,

    -- Hunter mode
    company_name        TEXT,
    company_url         TEXT,
    company_description TEXT,
    ideal_customer_profile TEXT,    -- JSON: {industry, size, roles, keywords}

    -- Seeker mode
    cv_text             TEXT,
    desired_role        TEXT,

    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prospects (
    id                  TEXT PRIMARY KEY,
    campaign_id         TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    company_name        TEXT NOT NULL,
    company_domain      TEXT,
    contact_name        TEXT,
    contact_email       TEXT,
    contact_role        TEXT,
    email_source        TEXT CHECK(email_source IN ('hunter', 'pattern_guess', 'manual')),
    email_verified      INTEGER DEFAULT 0,
    research_notes      TEXT,       -- JSON: {summary, news[], pain_points[], opportunities[]}
    unsubscribed_at     TEXT,           -- When prospect opted out
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'researching', 'contact_found',
                                         'email_drafted', 'email_approved', 'email_sent',
                                         'replied', 'bounced', 'opted_out', 'failed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails (
    id                  TEXT PRIMARY KEY,
    prospect_id         TEXT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id         TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    email_type          TEXT NOT NULL CHECK(email_type IN ('initial', 'followup_1', 'followup_2')),
    subject             TEXT NOT NULL,
    body_html           TEXT NOT NULL,
    body_text           TEXT NOT NULL,
    personalisation_points TEXT,    -- JSON array of research facts used
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft', 'pending_approval', 'approved',
                                         'sent', 'bounced', 'failed')),
    message_id          TEXT,           -- SMTP Message-ID for reply matching
    sent_at             TEXT,
    replied_at          TEXT,
    opened_at           TEXT,           -- First open detected via tracking pixel
    clicked_at          TEXT,           -- First link click via redirect tracking
    bounce_reason       TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS followup_schedule (
    id                  TEXT PRIMARY KEY,
    email_id            TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    prospect_id         TEXT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id         TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    scheduled_for       TEXT NOT NULL,
    followup_number     INTEGER NOT NULL CHECK(followup_number IN (1, 2)),
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'sent', 'cancelled')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS action_log (
    id                  TEXT PRIMARY KEY,
    campaign_id         TEXT REFERENCES campaigns(id),
    prospect_id         TEXT REFERENCES prospects(id),
    email_id            TEXT REFERENCES emails(id),
    action              TEXT NOT NULL,
    detail              TEXT,       -- JSON context
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_send_log (
    date                TEXT PRIMARY KEY,
    count               INTEGER NOT NULL DEFAULT 0,
    limit_for_day       INTEGER NOT NULL DEFAULT 5
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prospects_campaign ON prospects(campaign_id);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_emails_prospect ON emails(prospect_id);
CREATE INDEX IF NOT EXISTS idx_emails_campaign ON emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_followup_scheduled ON followup_schedule(scheduled_for, status);
CREATE INDEX IF NOT EXISTS idx_followup_campaign ON followup_schedule(campaign_id);
CREATE INDEX IF NOT EXISTS idx_action_log_campaign ON action_log(campaign_id);
CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);
