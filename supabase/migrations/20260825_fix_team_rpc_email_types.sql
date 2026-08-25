-- Supabase auth.users.email is varchar, while the public Team RPC contract
-- intentionally exposes email as text. PL/pgSQL RETURN QUERY requires an exact
-- type match, so cast all returned textual columns explicitly.

create or replace function public.privacy_gate_list_members(
    p_organization_id uuid
)
returns table (
    user_id uuid,
    email text,
    role text,
    status text,
    joined_at timestamptz
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
        m.user_id,
        coalesce(u.email, '')::text,
        m.role::text,
        m.status::text,
        m.joined_at
    from public.privacy_gate_memberships m
    left join auth.users u on u.id = m.user_id
    where m.organization_id = p_organization_id
    order by
        case m.role
            when 'owner' then 0
            when 'admin' then 1
            when 'manager' then 2
            else 3
        end,
        m.joined_at;
end;
$$;

create or replace function public.privacy_gate_list_devices(
    p_organization_id uuid
)
returns table (
    user_id uuid,
    email text,
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
        d.display_name::text,
        d.platform::text,
        d.app_version::text,
        d.status::text,
        d.last_policy_version,
        d.last_policy_sync_at
    from public.privacy_gate_devices d
    left join auth.users u on u.id = d.user_id
    where d.organization_id = p_organization_id
    order by d.last_policy_sync_at desc nulls last, d.display_name;
end;
$$;
