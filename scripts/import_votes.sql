-- Import voting data for 2026-01-28
-- Run this on the server: 
-- ssh root@77.110.105.104
-- cd /opt/wed-bobry-bot
-- docker-compose exec bot python -c "import sqlite3; exec(open('/app/import_votes.py').read())"
-- Or use sqlite3 directly:
-- sqlite3 data/data.db < import_votes.sql

-- Create session if not exists
INSERT OR IGNORE INTO sessions (chat_id, target_date, is_closed) 
VALUES (-1003689265922, '2026-01-28', 0);

-- Get the session_id (we'll use a subquery)
-- Insert YES votes
INSERT OR REPLACE INTO responses (session_id, chat_id, user_id, last_name, status, updated_at)
SELECT 
    (SELECT id FROM sessions WHERE chat_id = -1003689265922 AND target_date = '2026-01-28'),
    -1003689265922,
    user_id,
    last_name,
    'YES',
    datetime('now')
FROM (
    SELECT -1 as user_id, 'Черчинцев' as last_name UNION ALL
    SELECT -2, 'Антонцев' UNION ALL
    SELECT -3, 'Пономарь' UNION ALL
    SELECT -4, 'Лычагин' UNION ALL
    SELECT -5, 'Шевцов' UNION ALL
    SELECT -6, 'Яворовский' UNION ALL
    SELECT -7, 'Полещук' UNION ALL
    SELECT -8, 'Ровдо' UNION ALL
    SELECT -9, 'Гречаниченко' UNION ALL
    SELECT -10, 'Чих' UNION ALL
    SELECT -11, 'Тамразов'
);

-- Insert MAYBE votes
INSERT OR REPLACE INTO responses (session_id, chat_id, user_id, last_name, status, updated_at)
SELECT 
    (SELECT id FROM sessions WHERE chat_id = -1003689265922 AND target_date = '2026-01-28'),
    -1003689265922,
    user_id,
    last_name,
    'MAYBE',
    datetime('now')
FROM (
    SELECT -12 as user_id, 'Чикинев' as last_name UNION ALL
    SELECT -13, 'Массовец' UNION ALL
    SELECT -14, 'Козлов' UNION ALL
    SELECT -15, 'Пикунов' UNION ALL
    SELECT -16, 'Морозов' UNION ALL
    SELECT -17, 'Помазенков'
);

-- Insert NO votes
INSERT OR REPLACE INTO responses (session_id, chat_id, user_id, last_name, status, updated_at)
SELECT 
    (SELECT id FROM sessions WHERE chat_id = -1003689265922 AND target_date = '2026-01-28'),
    -1003689265922,
    user_id,
    last_name,
    'NO',
    datetime('now')
FROM (
    SELECT -18 as user_id, 'Быченков' as last_name UNION ALL
    SELECT -19, 'Бойцов' UNION ALL
    SELECT -20, 'Семенов'
);

-- Verify the import
SELECT 'Session:' as info;
SELECT * FROM sessions WHERE chat_id = -1003689265922 AND target_date = '2026-01-28';

SELECT 'Responses:' as info;
SELECT last_name, status FROM responses 
WHERE session_id = (SELECT id FROM sessions WHERE chat_id = -1003689265922 AND target_date = '2026-01-28')
ORDER BY 
    CASE status WHEN 'YES' THEN 1 WHEN 'MAYBE' THEN 2 WHEN 'NO' THEN 3 END,
    last_name;
