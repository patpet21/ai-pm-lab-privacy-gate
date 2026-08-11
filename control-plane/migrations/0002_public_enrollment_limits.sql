ALTER TABLE enrollment_sessions ADD COLUMN client_fingerprint TEXT;
CREATE INDEX enrollment_client_fingerprint_idx ON enrollment_sessions(client_fingerprint, created_at);
