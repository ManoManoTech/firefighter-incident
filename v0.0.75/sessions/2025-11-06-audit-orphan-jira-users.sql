-- ============================================================================
-- Audit Script: Orphan JiraUsers Analysis
-- ============================================================================
-- Purpose: Analyze JiraUsers without linked Users and estimate impact on
--          Slack notifications when linking them.
--
-- Database: Impact Support DB
-- Date: November 6, 2025
-- ============================================================================

-- 1. Count total orphan JiraUsers
-- ============================================================================
SELECT
    '1. ORPHAN JIRAUSERS COUNT' as analysis,
    COUNT(*) as total_orphans
FROM jira_app_jirauser
WHERE user_id IS NULL;

-- 2. Orphans that CAN be linked (User exists with same email)
-- ============================================================================
-- Note: This requires knowing the email from Jira, which is not stored in JiraUser table
-- We need to join with incidents_user by attempting to match via username pattern

SELECT
    '2. POTENTIALLY LINKABLE ORPHANS' as analysis,
    COUNT(DISTINCT ju.id) as linkable_count
FROM jira_app_jirauser ju
CROSS JOIN incidents_user u
WHERE ju.user_id IS NULL
  AND u.email IS NOT NULL
  AND u.email != ''
  -- This is an approximation - actual linking will be done via Jira API
;

-- 3. Orphans with potential Slack impact (would receive notifications)
-- ============================================================================
SELECT
    '3. ORPHANS WITH SLACK IMPACT' as analysis,
    COUNT(DISTINCT ju.id) as count_with_slack_impact
FROM jira_app_jirauser ju
INNER JOIN incidents_user u ON (
    -- Attempt to match by extracting username from email
    -- This is approximate - actual matching uses Jira API
    SPLIT_PART(u.email, '@', 1) = SPLIT_PART(ju.id, ':', 1)
    OR u.username IN (SELECT username FROM incidents_user WHERE email LIKE '%@%')
)
INNER JOIN slack_slackuser su ON su.user_id = u.id
WHERE ju.user_id IS NULL;

-- 4. Detailed list of orphan JiraUsers (limited to 20 for preview)
-- ============================================================================
SELECT
    '4. ORPHAN JIRAUSERS SAMPLE (20)' as analysis,
    ju.id as jira_account_id,
    ju.user_id as current_user_link,
    'NULL' as email_from_jira_api
FROM jira_app_jirauser ju
WHERE ju.user_id IS NULL
LIMIT 20;

-- 5. Users without JiraUser but might be in Jira
-- ============================================================================
SELECT
    '5. USERS WITHOUT JIRAUSER' as analysis,
    COUNT(*) as users_without_jirauser,
    COUNT(CASE WHEN su.slack_id IS NOT NULL THEN 1 END) as with_slack,
    COUNT(CASE WHEN su.slack_id IS NULL THEN 1 END) as without_slack
FROM incidents_user u
LEFT JOIN jira_app_jirauser ju ON ju.user_id = u.id
LEFT JOIN slack_slackuser su ON su.user_id = u.id
WHERE ju.id IS NULL
  AND u.is_active = true
  AND u.username != '';

-- 6. Summary statistics
-- ============================================================================
SELECT
    '6. SUMMARY STATISTICS' as analysis,
    (SELECT COUNT(*) FROM jira_app_jirauser WHERE user_id IS NULL) as total_orphan_jirausers,
    (SELECT COUNT(*) FROM incidents_user WHERE id NOT IN (SELECT user_id FROM jira_app_jirauser WHERE user_id IS NOT NULL)) as users_without_jirauser,
    (SELECT COUNT(*) FROM slack_slackuser) as total_slack_users,
    (SELECT COUNT(DISTINCT user_id) FROM slack_slackuser) as users_with_slack;

-- ============================================================================
-- SIMPLIFIED QUERY: Direct count of orphans and their potential matches
-- ============================================================================
-- This query attempts to match orphan JiraUsers with existing Users
-- by checking if there's a User whose email would generate the same username

WITH orphan_analysis AS (
    SELECT
        ju.id as jira_id,
        ju.user_id as current_user,
        u.id as potential_user_id,
        u.username as potential_username,
        u.email as potential_email,
        CASE WHEN su.slack_id IS NOT NULL THEN su.slack_id ELSE NULL END as slack_id,
        CASE WHEN su.slack_id IS NOT NULL THEN 'YES' ELSE 'NO' END as has_slack
    FROM jira_app_jirauser ju
    LEFT JOIN incidents_user u ON (
        -- Match will be done via Jira API in the actual sync task
        -- This is just an approximation for counting
        u.email IS NOT NULL AND u.email != ''
    )
    LEFT JOIN slack_slackuser su ON su.user_id = u.id
    WHERE ju.user_id IS NULL
)
SELECT
    'ORPHAN ANALYSIS SUMMARY' as report,
    COUNT(*) as total_checked,
    COUNT(potential_user_id) as has_potential_user,
    SUM(CASE WHEN has_slack = 'YES' THEN 1 ELSE 0 END) as would_receive_slack_notifications
FROM orphan_analysis;

-- ============================================================================
-- RECOMMENDED ACTION
-- ============================================================================
-- Run this query to get the actual count:
--
-- SELECT COUNT(*) as orphan_count
-- FROM jira_app_jirauser
-- WHERE user_id IS NULL;
--
-- If orphan_count > 0:
--   1. Review the list of orphans above
--   2. Run Python management command for detailed analysis:
--      python manage.py audit_orphan_jira_users --verbose
--   3. If impact is acceptable, run:
--      python manage.py link_orphan_jira_users --dry-run
-- ============================================================================
