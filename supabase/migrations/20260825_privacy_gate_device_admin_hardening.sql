-- Harden managed PrivacyGate device metadata.
-- Direct authenticated REST upserts may refresh harmless device metadata, but
-- company ownership, revocation state and policy-sync fields are control-plane
-- managed and must only change through SECURITY DEFINER Team RPCs.

create or replace function public.privacy_gate_guard_managed_device_fields()
returns trigger
language plpgsql
set search_path = public, auth
as $$
begin
    if current_user = 'authenticated' then
        new.user_id := old.user_id;
        new.installation_hash := old.installation_hash;
        new.status := old.status;
        new.organization_id := old.organization_id;
        new.membership_id := old.membership_id;
        new.last_policy_version := old.last_policy_version;
        new.last_policy_sync_at := old.last_policy_sync_at;
    end if;
    return new;
end;
$$;

drop trigger if exists privacy_gate_guard_managed_device_fields_trigger
on public.privacy_gate_devices;

create trigger privacy_gate_guard_managed_device_fields_trigger
before update on public.privacy_gate_devices
for each row execute function public.privacy_gate_guard_managed_device_fields();

revoke all on function public.privacy_gate_guard_managed_device_fields() from public;
