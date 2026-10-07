-- Desired default privileges for HEALTH.
-- This file is safe to run repeatedly.
-- Current live project was brought to this state manually through Supabase SQL Editor.

alter default privileges for role postgres in schema public
  revoke all privileges on tables
  from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences
  from anon, authenticated;

alter default privileges for role postgres in schema public
  revoke execute on functions
  from anon, authenticated;

-- PostgreSQL grants EXECUTE on newly created functions to PUBLIC globally by default.
-- This revoke must therefore be global, not schema-specific.
alter default privileges for role postgres
  revoke execute on functions
  from public;
