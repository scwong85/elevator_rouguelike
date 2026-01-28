CREATE TABLE IF NOT EXISTS scenario_stats (
    scenario_id TEXT NOT NULL,
    option_index INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scenario_id, option_index)
);
