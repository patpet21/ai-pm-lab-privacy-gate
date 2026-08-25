-- PrivacyGate Business / Enterprise control-plane foundation.
-- Privacy boundary: these tables contain identity, entitlement, device and policy
-- metadata only. Original/protected documents, restore mappings and connector
-- OAuth tokens remain on the employee device.

create extension if not exists pgcrypto;

create table if not exists public.privacy_gate_organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null check (char_length(btrim(name)) between 2 and 120),
    status text not null default 'active'
        check (status in ('active', 'suspended', 'closed')),
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now()
);

create table if not exists public.privacy_gate_memberships (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references public.privacy_gate_organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null
        check (role in ('owner', 'admin', 'manager', 'member')),
    status text not null default 'active'
        check (status in ('active', 'disabled', 'revoked')),
    joined_at timestamptz not null default now(),
    unique (organization_id, user_id)
);

create index if not exists privacy_gate_memberships_user_idx
    on public.privacy_gate_memberships(user_id, status);
create index if not exists privacy_gate_memberships_org_idx
    on public.privacy_gate_memberships(organization_id, status);

-- User-scoped privacy_gate_entitlements already exists in production and remains
-- the source of Basic/Pro access. Team plans get a separate organization table.
create table if not exists public.privacy_gate_org_entitlements (
    organization_id uuid primary key
        references public.privacy_gate_organizations(id) on delete cascade,
    plan_code text not null default 'business'
        check (plan_code in ('business', 'enterprise')),
    status text not null default 'trialing'
        check (status in ('trialing', 'active', 'past_due', 'canceled', 'suspended')),
    seat_limit integer not null default 5
        check (seat_limit between 1 and 100000),
    device_limit_per_member integer
        check (device_limit_per_member is null or device_limit_per_member between 1 and 100),
    feature_overrides jsonb not null default '{}'::jsonb,
    valid_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.privacy_gate_policies (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null unique
        references public.privacy_gate_organizations(id) on delete cascade,
    name text not null default 'Company Privacy Policy',
    active_version integer not null default 0 check (active_version >= 0),
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.privacy_gate_policy_versions (
    id uuid primary key default gen_random_uuid(),
    policy_id uuid not null
        references public.privacy_gate_policies(id) on delete cascade,
    organization_id uuid not null
        references public.privacy_gate_organizations(id) on delete cascade,
    version integer not null check (version >= 1),
    policy_json jsonb not null,
    policy_sha256 text not null,
    created_by uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    unique (policy_id, version)
);

create index if not exists privacy_gate_policy_versions_org_idx
    on public.privacy_gate_policy_versions(organization_id, version desc);

create table if not exists public.privacy_gate_invitations (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references public.privacy_gate_organizations(id) on delete cascade,
    token_hash text not null unique,
    role text not null
        check (role in ('admin', 'manager', 'member')),
    status text not null default 'pending'
        check (status in ('pending', 'used', 'revoked', 'expired')),
    expires_at timestamptz not null,
    created_by uuid not null references auth.users(id) on delete restrict,
    used_by uuid references auth.users(id) on delete set null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists privacy_gate_invitations_org_idx
    on public.privacy_gate_invitations(organization_id, status, expires_at);

-- Existing account code already writes to privacy_gate_devices. Create the
-- baseline only for new deployments, then add team metadata idempotently.
create table if not exists public.privacy_gate_devices (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    installation_hash text not null unique,
    display_name text not null default 'This PC',
    platform text not null default '',
    app_version text not null default '',
    status text not null default 'active'
        check (status in ('active', 'disabled', 'revoked')),
    created_at timestamptz not null default now()
);

alter table public.privacy_gate_devices
    add column if not exists organization_id uuid
        references public.privacy_gate_organizations(id) on delete set null;
alter table public.privacy_gate_devices
    add column if not exists membership_id uuid
        references public.privacy_gate_memberships(id) on delete set null;
alter table public.privacy_gate_devices
    add column if not exists last_policy_version integer;
alter table public.privacy_gate_devices
    add column if not exists last_policy_sync_at timestamptz;

-- Existing production schema initially allowed only active/revoked. Business
-- adds a reversible disabled state without invalidating either existing value.
alter table public.privacy_gate_devices
    drop constraint if exists privacy_gate_devices_status_check;
alter table public.privacy_gate_devices
    add constraint privacy_gate_devices_status_check
    check (status in ('active', 'disabled', 'revoked'));

create index if not exists privacy_gate_devices_org_idx
    on public.privacy_gate_devices(organization_id, status);

create or replace function public.privacy_gate_is_org_member(p_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.privacy_gate_memberships m
        where m.organization_id = p_organization_id
          and m.user_id = auth.uid()
          and m.status = 'active'
    );
$$;

create or replace function public.privacy_gate_has_org_role(
    p_organization_id uuid,
    p_roles text[]
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.privacy_gate_memberships m
        where m.organization_id = p_organization_id
          and m.user_id = auth.uid()
          and m.status = 'active'
          and m.role = any(p_roles)
    );
$$;

alter table public.privacy_gate_organizations enable row level security;
alter table public.privacy_gate_memberships enable row level security;
alter table public.privacy_gate_org_entitlements enable row level security;
alter table public.privacy_gate_policies enable row level security;
alter table public.privacy_gate_policy_versions enable row level security;
alter table public.privacy_gate_invitations enable row level security;
alter table public.privacy_gate_devices enable row level security;

drop policy if exists "privacy_gate_org_select_member" on public.privacy_gate_organizations;
create policy "privacy_gate_org_select_member"
on public.privacy_gate_organizations for select
to authenticated
using (public.privacy_gate_is_org_member(id));

drop policy if exists "privacy_gate_membership_select" on public.privacy_gate_memberships;
create policy "privacy_gate_membership_select"
on public.privacy_gate_memberships for select
to authenticated
using (
    user_id = auth.uid()
    or public.privacy_gate_has_org_role(
        organization_id, array['owner', 'admin', 'manager']
    )
);

-- Keep the existing user-scoped privacy_gate_entitlements table and its
-- current RLS policy untouched. It remains the source of Basic/Pro entitlement.
drop policy if exists "privacy_gate_org_entitlement_select" on public.privacy_gate_org_entitlements;
create policy "privacy_gate_org_entitlement_select"
on public.privacy_gate_org_entitlements for select
to authenticated
using (public.privacy_gate_is_org_member(organization_id));

drop policy if exists "privacy_gate_policy_select" on public.privacy_gate_policies;
create policy "privacy_gate_policy_select"
on public.privacy_gate_policies for select
to authenticated
using (public.privacy_gate_is_org_member(organization_id));

drop policy if exists "privacy_gate_policy_version_select" on public.privacy_gate_policy_versions;
create policy "privacy_gate_policy_version_select"
on public.privacy_gate_policy_versions for select
to authenticated
using (public.privacy_gate_is_org_member(organization_id));

drop policy if exists "privacy_gate_invitation_select_admin" on public.privacy_gate_invitations;
create policy "privacy_gate_invitation_select_admin"
on public.privacy_gate_invitations for select
to authenticated
using (
    public.privacy_gate_has_org_role(
        organization_id, array['owner', 'admin']
    )
);

drop policy if exists "privacy_gate_device_select" on public.privacy_gate_devices;
create policy "privacy_gate_device_select"
on public.privacy_gate_devices for select
to authenticated
using (
    user_id = auth.uid()
    or (
        organization_id is not null
        and public.privacy_gate_has_org_role(
            organization_id, array['owner', 'admin', 'manager']
        )
    )
);

-- Preserve the current per-user device registration behavior used by account
-- sign-in while the team RPCs attach organization metadata.
drop policy if exists "privacy_gate_device_insert_own" on public.privacy_gate_devices;
create policy "privacy_gate_device_insert_own"
on public.privacy_gate_devices for insert
to authenticated
with check (user_id = auth.uid());

drop policy if exists "privacy_gate_device_update_own" on public.privacy_gate_devices;
create policy "privacy_gate_device_update_own"
on public.privacy_gate_devices for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create or replace function public.privacy_gate_create_business_workspace(
    p_name text,
    p_seat_limit integer default 5
)
returns uuid
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_user uuid := auth.uid();
    v_org uuid;
    v_policy uuid;
    v_name text := btrim(coalesce(p_name, ''));
    v_seats integer := greatest(2, least(coalesce(p_seat_limit, 5), 100));
    v_default_policy jsonb;
begin
    if v_user is null then
        raise exception 'Authentication required';
    end if;
    if char_length(v_name) < 2 or char_length(v_name) > 120 then
        raise exception 'Organization name must be between 2 and 120 characters';
    end if;
    if exists (
        select 1 from public.privacy_gate_memberships
        where user_id = v_user and status = 'active'
    ) then
        raise exception 'This account already belongs to an active PrivacyGate organization';
    end if;

    insert into public.privacy_gate_organizations(name, created_by)
    values (v_name, v_user)
    returning id into v_org;

    insert into public.privacy_gate_memberships(
        organization_id, user_id, role, status
    )
    values (v_org, v_user, 'owner', 'active');

    -- Self-service Business is a trial until the future billing control plane
    -- promotes it to active. Enterprise is intentionally never self-provisioned.
    insert into public.privacy_gate_org_entitlements(
        organization_id, plan_code, status, seat_limit,
        device_limit_per_member
    )
    values (
        v_org, 'business', 'trialing', v_seats, 2
    );

    insert into public.privacy_gate_policies(
        organization_id, name, active_version, created_by
    )
    values (
        v_org, 'Company Privacy Policy', 1, v_user
    )
    returning id into v_policy;

    v_default_policy := jsonb_build_object(
        'allowed_ai', jsonb_build_object(
            'chatgpt', true,
            'claude', true,
            'other', false
        ),
        'allowed_connectors', jsonb_build_object(
            'gmail', true,
            'google_drive', true,
            'clickup', true,
            'asana', true,
            'trello', true,
            'notion', false,
            'monday', false,
            'jira', false
        ),
        'protection_rules', jsonb_build_object(
            'US_SSN', 'required_protect',
            'US_BANK_NUMBER', 'required_protect',
            'US_ROUTING_NUMBER', 'required_protect',
            'CREDIT_CARD', 'required_protect',
            'EMAIL_ADDRESS', 'default_protect',
            'PHONE_NUMBER', 'default_protect',
            'PERSON', 'user_choice',
            'STREET_ADDRESS', 'user_choice',
            'LOCATION', 'user_choice',
            'MONEY_AMOUNT', 'allow',
            'CUSTOMER_ID', 'default_protect',
            'EMPLOYEE_ID', 'default_protect'
        )
    );

    insert into public.privacy_gate_policy_versions(
        policy_id, organization_id, version, policy_json,
        policy_sha256, created_by
    )
    values (
        v_policy,
        v_org,
        1,
        v_default_policy,
        encode(digest(v_default_policy::text, 'sha256'), 'hex'),
        v_user
    );

    return v_org;
end;
$$;

create or replace function public.privacy_gate_create_invitation(
    p_organization_id uuid,
    p_role text default 'member',
    p_expires_hours integer default 72
)
returns text
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_user uuid := auth.uid();
    v_code text;
    v_hours integer := greatest(1, least(coalesce(p_expires_hours, 72), 720));
begin
    if v_user is null then
        raise exception 'Authentication required';
    end if;
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin']
    ) then
        raise exception 'Organization admin permission required';
    end if;
    if p_role not in ('admin', 'manager', 'member') then
        raise exception 'Invalid invitation role';
    end if;

    v_code := 'PG-' || upper(encode(gen_random_bytes(12), 'hex'));

    insert into public.privacy_gate_invitations(
        organization_id, token_hash, role, status, expires_at, created_by
    )
    values (
        p_organization_id,
        encode(digest(v_code, 'sha256'), 'hex'),
        p_role,
        'pending',
        now() + make_interval(hours => v_hours),
        v_user
    );

    return v_code;
end;
$$;

create or replace function public.privacy_gate_accept_invitation(
    p_code text,
    p_installation_hash text,
    p_display_name text,
    p_platform text,
    p_app_version text
)
returns uuid
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_user uuid := auth.uid();
    v_inv public.privacy_gate_invitations%rowtype;
    v_membership uuid;
    v_seat_limit integer;
    v_active_count integer;
    v_policy_version integer;
begin
    if v_user is null then
        raise exception 'Authentication required';
    end if;
    if char_length(btrim(coalesce(p_code, ''))) < 10 then
        raise exception 'Invalid invitation code';
    end if;

    select *
    into v_inv
    from public.privacy_gate_invitations
    where token_hash = encode(digest(btrim(p_code), 'sha256'), 'hex')
      and status = 'pending'
      and expires_at > now()
    for update;

    if not found then
        raise exception 'Invitation is invalid, expired or already used';
    end if;

    if exists (
        select 1
        from public.privacy_gate_memberships
        where user_id = v_user
          and status = 'active'
          and organization_id <> v_inv.organization_id
    ) then
        raise exception 'This account already belongs to another active PrivacyGate organization';
    end if;

    select seat_limit
    into v_seat_limit
    from public.privacy_gate_org_entitlements
    where organization_id = v_inv.organization_id
      and plan_code in ('business', 'enterprise')
      and status in ('trialing', 'active');

    if v_seat_limit is null then
        raise exception 'Organization entitlement is not active';
    end if;

    select count(*)
    into v_active_count
    from public.privacy_gate_memberships
    where organization_id = v_inv.organization_id
      and status = 'active'
      and user_id <> v_user;

    if v_active_count >= v_seat_limit then
        raise exception 'No PrivacyGate seats are available for this organization';
    end if;

    insert into public.privacy_gate_memberships(
        organization_id, user_id, role, status
    )
    values (
        v_inv.organization_id, v_user, v_inv.role, 'active'
    )
    on conflict (organization_id, user_id)
    do update set role = excluded.role, status = 'active'
    returning id into v_membership;

    update public.privacy_gate_invitations
    set status = 'used', used_by = v_user, used_at = now()
    where id = v_inv.id;

    select active_version
    into v_policy_version
    from public.privacy_gate_policies
    where organization_id = v_inv.organization_id and status = 'active';

    if exists (
        select 1 from public.privacy_gate_devices
        where installation_hash = p_installation_hash
          and user_id <> v_user
    ) then
        raise exception 'This device identity is already bound to another account';
    end if;

    insert into public.privacy_gate_devices(
        user_id, installation_hash, display_name, platform, app_version,
        status, organization_id, membership_id, last_policy_version,
        last_policy_sync_at
    )
    values (
        v_user,
        p_installation_hash,
        coalesce(nullif(btrim(p_display_name), ''), 'This PC'),
        coalesce(p_platform, ''),
        coalesce(p_app_version, ''),
        'active',
        v_inv.organization_id,
        v_membership,
        v_policy_version,
        now()
    )
    on conflict (installation_hash)
    do update set
        display_name = excluded.display_name,
        platform = excluded.platform,
        app_version = excluded.app_version,
        status = 'active',
        organization_id = excluded.organization_id,
        membership_id = excluded.membership_id,
        last_policy_version = excluded.last_policy_version,
        last_policy_sync_at = excluded.last_policy_sync_at;

    return v_inv.organization_id;
end;
$$;

create or replace function public.privacy_gate_sync_team_device(
    p_organization_id uuid,
    p_installation_hash text,
    p_display_name text,
    p_platform text,
    p_app_version text,
    p_policy_version integer
)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_user uuid := auth.uid();
    v_membership uuid;
begin
    if v_user is null then
        raise exception 'Authentication required';
    end if;

    select id
    into v_membership
    from public.privacy_gate_memberships
    where organization_id = p_organization_id
      and user_id = v_user
      and status = 'active';

    if v_membership is null then
        raise exception 'Active organization membership required';
    end if;

    if exists (
        select 1 from public.privacy_gate_devices
        where installation_hash = p_installation_hash
          and user_id <> v_user
    ) then
        raise exception 'This device identity is already bound to another account';
    end if;

    insert into public.privacy_gate_devices(
        user_id, installation_hash, display_name, platform, app_version,
        status, organization_id, membership_id, last_policy_version,
        last_policy_sync_at
    )
    values (
        v_user,
        p_installation_hash,
        coalesce(nullif(btrim(p_display_name), ''), 'This PC'),
        coalesce(p_platform, ''),
        coalesce(p_app_version, ''),
        'active',
        p_organization_id,
        v_membership,
        p_policy_version,
        now()
    )
    on conflict (installation_hash)
    do update set
        display_name = excluded.display_name,
        platform = excluded.platform,
        app_version = excluded.app_version,
        organization_id = excluded.organization_id,
        membership_id = excluded.membership_id,
        last_policy_version = excluded.last_policy_version,
        last_policy_sync_at = excluded.last_policy_sync_at;
end;
$$;

create or replace function public.privacy_gate_publish_policy(
    p_organization_id uuid,
    p_policy jsonb,
    p_name text default 'Company Privacy Policy'
)
returns integer
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_user uuid := auth.uid();
    v_policy_id uuid;
    v_next integer;
begin
    if v_user is null then
        raise exception 'Authentication required';
    end if;
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin']
    ) then
        raise exception 'Organization admin permission required';
    end if;
    if jsonb_typeof(p_policy) <> 'object'
       or jsonb_typeof(p_policy->'allowed_ai') <> 'object'
       or jsonb_typeof(p_policy->'allowed_connectors') <> 'object'
       or jsonb_typeof(p_policy->'protection_rules') <> 'object' then
        raise exception 'Invalid company policy shape';
    end if;

    select id, active_version + 1
    into v_policy_id, v_next
    from public.privacy_gate_policies
    where organization_id = p_organization_id
    for update;

    if v_policy_id is null then
        insert into public.privacy_gate_policies(
            organization_id, name, active_version, created_by
        )
        values (
            p_organization_id,
            coalesce(nullif(btrim(p_name), ''), 'Company Privacy Policy'),
            0,
            v_user
        )
        returning id, 1 into v_policy_id, v_next;
    end if;

    insert into public.privacy_gate_policy_versions(
        policy_id, organization_id, version, policy_json,
        policy_sha256, created_by
    )
    values (
        v_policy_id,
        p_organization_id,
        v_next,
        p_policy,
        encode(digest(p_policy::text, 'sha256'), 'hex'),
        v_user
    );

    update public.privacy_gate_policies
    set
        name = coalesce(nullif(btrim(p_name), ''), name),
        active_version = v_next,
        status = 'active',
        updated_at = now()
    where id = v_policy_id;

    return v_next;
end;
$$;

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
        coalesce(u.email, ''),
        m.role,
        m.status,
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
        coalesce(u.email, ''),
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

create or replace function public.privacy_gate_set_member_status(
    p_organization_id uuid,
    p_user_id uuid,
    p_status text
)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
begin
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin']
    ) then
        raise exception 'Organization admin permission required';
    end if;
    if p_status not in ('active', 'disabled', 'revoked') then
        raise exception 'Invalid member status';
    end if;
    if exists (
        select 1
        from public.privacy_gate_memberships
        where organization_id = p_organization_id
          and user_id = p_user_id
          and role = 'owner'
    ) then
        raise exception 'The organization owner cannot be disabled by this action';
    end if;

    update public.privacy_gate_memberships
    set status = p_status
    where organization_id = p_organization_id and user_id = p_user_id;

    if p_status <> 'active' then
        update public.privacy_gate_devices
        set status = 'disabled'
        where organization_id = p_organization_id and user_id = p_user_id;
    end if;
end;
$$;

create or replace function public.privacy_gate_set_device_status(
    p_organization_id uuid,
    p_installation_hash text,
    p_status text
)
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
begin
    if not public.privacy_gate_has_org_role(
        p_organization_id, array['owner', 'admin']
    ) then
        raise exception 'Organization admin permission required';
    end if;
    if p_status not in ('active', 'disabled', 'revoked') then
        raise exception 'Invalid device status';
    end if;

    update public.privacy_gate_devices
    set status = p_status
    where organization_id = p_organization_id
      and installation_hash = p_installation_hash;
end;
$$;

revoke all on function public.privacy_gate_is_org_member(uuid) from public;
revoke all on function public.privacy_gate_has_org_role(uuid, text[]) from public;
revoke all on function public.privacy_gate_create_business_workspace(text, integer) from public;
revoke all on function public.privacy_gate_create_invitation(uuid, text, integer) from public;
revoke all on function public.privacy_gate_accept_invitation(text, text, text, text, text) from public;
revoke all on function public.privacy_gate_sync_team_device(uuid, text, text, text, text, integer) from public;
revoke all on function public.privacy_gate_publish_policy(uuid, jsonb, text) from public;
revoke all on function public.privacy_gate_list_members(uuid) from public;
revoke all on function public.privacy_gate_list_devices(uuid) from public;
revoke all on function public.privacy_gate_set_member_status(uuid, uuid, text) from public;
revoke all on function public.privacy_gate_set_device_status(uuid, text, text) from public;

grant execute on function public.privacy_gate_is_org_member(uuid) to authenticated;
grant execute on function public.privacy_gate_has_org_role(uuid, text[]) to authenticated;
grant execute on function public.privacy_gate_create_business_workspace(text, integer) to authenticated;
grant execute on function public.privacy_gate_create_invitation(uuid, text, integer) to authenticated;
grant execute on function public.privacy_gate_accept_invitation(text, text, text, text, text) to authenticated;
grant execute on function public.privacy_gate_sync_team_device(uuid, text, text, text, text, integer) to authenticated;
grant execute on function public.privacy_gate_publish_policy(uuid, jsonb, text) to authenticated;
grant execute on function public.privacy_gate_list_members(uuid) to authenticated;
grant execute on function public.privacy_gate_list_devices(uuid) to authenticated;
grant execute on function public.privacy_gate_set_member_status(uuid, uuid, text) to authenticated;
grant execute on function public.privacy_gate_set_device_status(uuid, text, text) to authenticated;

grant select on public.privacy_gate_organizations to authenticated;
grant select on public.privacy_gate_memberships to authenticated;
grant select on public.privacy_gate_org_entitlements to authenticated;
grant select on public.privacy_gate_policies to authenticated;
grant select on public.privacy_gate_policy_versions to authenticated;
grant select on public.privacy_gate_invitations to authenticated;
grant select, insert, update on public.privacy_gate_devices to authenticated;
