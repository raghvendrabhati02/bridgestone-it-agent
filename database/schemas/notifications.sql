CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,

    ticket_id INTEGER REFERENCES tickets(id),

    user_id INTEGER REFERENCES users(id),

    notification_type VARCHAR(100),

    message TEXT,

    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
