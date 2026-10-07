-- Runs once, when the Postgres volume is first created. The main `bane` database is created
-- from POSTGRES_DB; this adds the database the backend tests use.
CREATE DATABASE bane_test OWNER bane;
