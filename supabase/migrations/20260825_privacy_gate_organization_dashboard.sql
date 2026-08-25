-- Role-aware Organization dashboard support.
-- No document metadata is introduced by this migration.

drop function if exists public.privacy_gate_list_devices(uuid);

create function public.privacy_gate_list_devices(
    p_organization_id uuid
)
returns table (
    user_id uuid,
    email text,
    installation_hash text,
    display_name text,
    platform text,
    app_version text,
    status text,
    last_policy_version integer,
    last_policy_sync_at timestamptz
)
language plpgsql
stable
security definer
set search_path = public, auth
as $$
begin
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin', 'manager']
    ) then
        raise exception 'Manager permission required';
    end if;

    return query
    select
        d.user_id,
        coalesce(u.email, '')::text,
        d.installation_hash,
        d.display_name,
        d.platform,
        d.app_version,
        d.status,
        d.last_policy_version,
        d.last_policy_sync_at
    from public.privacy_gate_devices d
    left join auth.users u on u.id = d.user_id
    where d.organization_id = p_organization_id
    order by d.last_policy_sync_at desc nulls last, d.display_name;
end;
$$;

create or replace function public.privacy_gate_set_member_role(
    p_organization_id uuid,
    p_user_id uuid,
    p_role text
)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_current_role text;
begin
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin']
    ) then
        raise exception 'Organization admin permission required';
    end if;

    if p_role not in ('admin', 'manager', 'member') then
        raise exception 'Invalid member role';
    end if;

    select role
    into v_current_role
    from public.privacy_gate_memberships
    where organization_id = p_organization_id
      and user_id = p_user_id;

    if v_current_role is null then
        raise exception 'Organization member not found';
    end if;

    if v_current_role = 'owner' then
        raise exception 'The organization owner role cannot be changed';
    end if;

    update public.privacy_gate_memberships
    set role = p_role
    where organization_id = p_organization_id
      and user_id = p_user_id;
end;
$$;

revoke all on function public.privacy_gate_list_devices(uuid) from public;
revoke all on function public.privacy_gate_set_member_role(uuid, uuid, text) from public;

grant execute on function public.privacy_gate_list_devices(uuid) to authenticated;
grant execute on function public.privacy_gate_set_member_role(uuid, uuid, text) to authenticated;
