CREATE TABLE sla_tracking (
    id SERIAL PRIMARY KEY,

    ticket_id INTEGER REFERENCES tickets(id),

    target_resolution_time TIMESTAMP,

    escalation_level INTEGER DEFAULT 0,

    sla_status VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
