CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,

    user_id INTEGER REFERENCES users(id),

    ticket_id INTEGER REFERENCES tickets(id),

    sender VARCHAR(20),

    message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
