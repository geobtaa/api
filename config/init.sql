CREATE DATABASE btaa_geospatial_api;
CREATE USER btaa_geospatial_api_user WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE btaa_geospatial_api TO btaa_geospatial_api_user;