CREATE DATABASE btaa_data_api;
CREATE USER btaa_data_api_user WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE btaa_data_api TO btaa_data_api_user;