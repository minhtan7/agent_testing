-- Grant permissions to the lumora user
ALTER USER lumora WITH CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE lumora TO lumora;
GRANT ALL PRIVILEGES ON SCHEMA public TO lumora;
ALTER USER lumora WITH SUPERUSER;
