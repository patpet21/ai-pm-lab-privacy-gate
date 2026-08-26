-- Fix pgcrypto function resolution inside PrivacyGate SECURITY DEFINER RPCs.
-- Supabase installs pgcrypto in the extensions schema. These RPCs intentionally
-- use a restricted search_path, so include extensions explicitly instead of
-- exposing broader schemas.

create extension if not exists pgcrypto with schema extensions;

alter function public.privacy_gate_create_business_workspace(text, integer)
    set search_path = public, auth, extensions;

alter function public.privacy_gate_create_invitation(uuid, text, integer)
    set search_path = public, auth, extensions;

alter function public.privacy_gate_accept_invitation(text, text, text, text, text)
    set search_path = public, auth, extensions;

alter function public.privacy_gate_publish_policy(uuid, jsonb, text)
    set search_path = public, auth, extensions;
