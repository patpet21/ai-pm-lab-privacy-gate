-- PrivacyGate multi-workspace foundation.
-- One PrivacyGate account can keep Personal plus multiple organization memberships.
-- Device/org status is scoped per workspace so offboarding from one company never
-- disables the user's Personal workspace or another company workspace.

create table if not exists public.privacy_gate_device_workspaces (
    organization_id uuid not null references public.privacy_gate_organizations(id) on delete cascade,
    membership_id uuid not null references public.privacy_gate_memberships(id) on delete cascade,
    device_id uuid not null references public.privacy_gate_devices(id) on delete cascade,
    status text not null default 'active' check (status in ('active', 'disabled', 'revoked')),
    last_policy_version integer,
    last_policy_sync_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, device_id),
    unique (organization_id, membership_id, device_id)
);

create index if not exists privacy_gate_device_workspaces_membership_idx on public.privacy_gate_device_workspaces(membership_id, status);
create index if not exists privacy_gate_device_workspaces_device_idx on public.privacy_gate_device_workspaces(device_id, status);

insert into public.privacy_gate_device_workspaces(organization_id,membership_id,device_id,status,last_policy_version,last_policy_sync_at,created_at,updated_at)
select d.organization_id,d.membership_id,d.id,d.status,d.last_policy_version,d.last_policy_sync_at,coalesce(d.created_at,now()),coalesce(d.updated_at,now())
from public.privacy_gate_devices d
where d.organization_id is not null and d.membership_id is not null
on conflict (organization_id, device_id) do update set membership_id=excluded.membership_id,status=excluded.status,last_policy_version=excluded.last_policy_version,last_policy_sync_at=excluded.last_policy_sync_at,updated_at=now();

alter table public.privacy_gate_device_workspaces enable row level security;
drop policy if exists "privacy_gate_device_workspace_select" on public.privacy_gate_device_workspaces;
create policy "privacy_gate_device_workspace_select" on public.privacy_gate_device_workspaces for select to authenticated
using (
    exists (select 1 from public.privacy_gate_devices d where d.id=device_id and d.user_id=auth.uid())
    or public.privacy_gate_has_org_role(organization_id,array['owner','admin','manager'])
);

create or replace function public.privacy_gate_create_business_workspace(p_name text,p_seat_limit integer default 5)
returns uuid language plpgsql security definer set search_path=public,auth as $$
declare
    v_user uuid:=auth.uid(); v_org uuid; v_policy uuid;
    v_name text:=btrim(coalesce(p_name,''));
    v_seats integer:=greatest(2,least(coalesce(p_seat_limit,5),100));
    v_default_policy jsonb;
begin
    if v_user is null then raise exception 'Authentication required'; end if;
    if char_length(v_name)<2 or char_length(v_name)>120 then raise exception 'Organization name must be between 2 and 120 characters'; end if;
    insert into public.privacy_gate_organizations(name,created_by) values(v_name,v_user) returning id into v_org;
    insert into public.privacy_gate_memberships(organization_id,user_id,role,status) values(v_org,v_user,'owner','active');
    insert into public.privacy_gate_org_entitlements(organization_id,plan_code,status,seat_limit,device_limit_per_member) values(v_org,'business','trialing',v_seats,2);
    insert into public.privacy_gate_policies(organization_id,name,active_version,created_by) values(v_org,'Company Privacy Policy',1,v_user) returning id into v_policy;
    v_default_policy:=jsonb_build_object(
      'allowed_ai',jsonb_build_object('chatgpt',true,'claude',true,'other',false),
      'allowed_connectors',jsonb_build_object('gmail',true,'google_drive',true,'clickup',true,'asana',true,'trello',true,'notion',false,'monday',false,'jira',false),
      'protection_rules',jsonb_build_object('US_SSN','required_protect','US_BANK_NUMBER','required_protect','US_ROUTING_NUMBER','required_protect','CREDIT_CARD','required_protect','EMAIL_ADDRESS','default_protect','PHONE_NUMBER','default_protect','PERSON','user_choice','STREET_ADDRESS','user_choice','LOCATION','user_choice','MONEY_AMOUNT','allow','CUSTOMER_ID','default_protect','EMPLOYEE_ID','default_protect')
    );
    insert into public.privacy_gate_policy_versions(policy_id,organization_id,version,policy_json,policy_sha256,created_by)
    values(v_policy,v_org,1,v_default_policy,encode(digest(v_default_policy::text,'sha256'),'hex'),v_user);
    return v_org;
end; $$;

create or replace function public.privacy_gate_accept_invitation(p_code text,p_installation_hash text,p_display_name text,p_platform text,p_app_version text)
returns uuid language plpgsql security definer set search_path=public,auth as $$
declare
    v_user uuid:=auth.uid(); v_inv public.privacy_gate_invitations%rowtype; v_membership uuid;
    v_seat_limit integer; v_active_count integer; v_policy_version integer; v_device uuid;
begin
    if v_user is null then raise exception 'Authentication required'; end if;
    if char_length(btrim(coalesce(p_code,'')))<10 then raise exception 'Invalid invitation code'; end if;
    select * into v_inv from public.privacy_gate_invitations where token_hash=encode(digest(btrim(p_code),'sha256'),'hex') and status='pending' and expires_at>now() for update;
    if not found then raise exception 'Invitation is invalid, expired or already used'; end if;
    select seat_limit into v_seat_limit from public.privacy_gate_org_entitlements where organization_id=v_inv.organization_id and plan_code in('business','enterprise') and status in('trialing','active');
    if v_seat_limit is null then raise exception 'Organization entitlement is not active'; end if;
    select count(*) into v_active_count from public.privacy_gate_memberships where organization_id=v_inv.organization_id and status='active' and user_id<>v_user;
    if v_active_count>=v_seat_limit then raise exception 'No PrivacyGate seats are available for this organization'; end if;
    insert into public.privacy_gate_memberships(organization_id,user_id,role,status) values(v_inv.organization_id,v_user,v_inv.role,'active')
      on conflict(organization_id,user_id) do update set role=excluded.role,status='active' returning id into v_membership;
    update public.privacy_gate_invitations set status='used',used_by=v_user,used_at=now() where id=v_inv.id;
    select active_version into v_policy_version from public.privacy_gate_policies where organization_id=v_inv.organization_id and status='active';
    if exists(select 1 from public.privacy_gate_devices where installation_hash=p_installation_hash and user_id<>v_user) then raise exception 'This device identity is already bound to another account'; end if;
    insert into public.privacy_gate_devices(user_id,installation_hash,display_name,platform,app_version,status)
      values(v_user,p_installation_hash,coalesce(nullif(btrim(p_display_name),''),'This PC'),coalesce(p_platform,''),coalesce(p_app_version,''),'active')
      on conflict(installation_hash) do update set display_name=excluded.display_name,platform=excluded.platform,app_version=excluded.app_version returning id into v_device;
    insert into public.privacy_gate_device_workspaces(organization_id,membership_id,device_id,status,last_policy_version,last_policy_sync_at)
      values(v_inv.organization_id,v_membership,v_device,'active',v_policy_version,now())
      on conflict(organization_id,device_id) do update set membership_id=excluded.membership_id,status='active',last_policy_version=excluded.last_policy_version,last_policy_sync_at=excluded.last_policy_sync_at,updated_at=now();
    update public.privacy_gate_devices set organization_id=coalesce(organization_id,v_inv.organization_id),membership_id=coalesce(membership_id,v_membership) where id=v_device;
    return v_inv.organization_id;
end; $$;

create or replace function public.privacy_gate_sync_team_device(p_organization_id uuid,p_installation_hash text,p_display_name text,p_platform text,p_app_version text,p_policy_version integer)
returns void language plpgsql security definer set search_path=public,auth as $$
declare
    v_user uuid:=auth.uid(); v_membership uuid; v_device uuid; v_device_limit integer; v_bound_devices integer;
begin
    if v_user is null then raise exception 'Authentication required'; end if;
    select id into v_membership from public.privacy_gate_memberships where organization_id=p_organization_id and user_id=v_user and status='active';
    if v_membership is null then raise exception 'Active organization membership required'; end if;
    if exists(select 1 from public.privacy_gate_devices where installation_hash=p_installation_hash and user_id<>v_user) then raise exception 'This device identity is already bound to another account'; end if;
    insert into public.privacy_gate_devices(user_id,installation_hash,display_name,platform,app_version,status)
      values(v_user,p_installation_hash,coalesce(nullif(btrim(p_display_name),''),'This PC'),coalesce(p_platform,''),coalesce(p_app_version,''),'active')
      on conflict(installation_hash) do update set display_name=excluded.display_name,platform=excluded.platform,app_version=excluded.app_version returning id into v_device;
    select device_limit_per_member into v_device_limit from public.privacy_gate_org_entitlements where organization_id=p_organization_id and status in('trialing','active');
    if v_device_limit is not null then
      select count(*) into v_bound_devices from public.privacy_gate_device_workspaces dw where dw.organization_id=p_organization_id and dw.membership_id=v_membership and dw.device_id<>v_device and dw.status='active';
      if v_bound_devices>=v_device_limit then raise exception 'Device limit reached for this workspace member'; end if;
    end if;
    insert into public.privacy_gate_device_workspaces(organization_id,membership_id,device_id,status,last_policy_version,last_policy_sync_at)
      values(p_organization_id,v_membership,v_device,'active',p_policy_version,now())
      on conflict(organization_id,device_id) do update set membership_id=excluded.membership_id,last_policy_version=excluded.last_policy_version,last_policy_sync_at=excluded.last_policy_sync_at,updated_at=now();
    update public.privacy_gate_devices set organization_id=coalesce(organization_id,p_organization_id),membership_id=coalesce(membership_id,v_membership) where id=v_device;
end; $$;

drop function if exists public.privacy_gate_list_devices(uuid);
create function public.privacy_gate_list_devices(p_organization_id uuid)
returns table(user_id uuid,email text,installation_hash text,display_name text,platform text,app_version text,status text,last_policy_version integer,last_policy_sync_at timestamptz)
language plpgsql security definer set search_path=public,auth as $$
begin
    if not public.privacy_gate_has_org_role(p_organization_id,array['owner','admin','manager']) then raise exception 'Organization management permission required'; end if;
    return query select d.user_id,u.email::text,d.installation_hash,d.display_name,d.platform,d.app_version,dw.status,dw.last_policy_version,dw.last_policy_sync_at
      from public.privacy_gate_device_workspaces dw join public.privacy_gate_devices d on d.id=dw.device_id left join auth.users u on u.id=d.user_id
      where dw.organization_id=p_organization_id order by lower(coalesce(u.email::text,'')),lower(d.display_name);
end; $$;

create or replace function public.privacy_gate_set_device_status(p_organization_id uuid,p_installation_hash text,p_status text)
returns void language plpgsql security definer set search_path=public,auth as $$
begin
    if not public.privacy_gate_has_org_role(p_organization_id,array['owner','admin']) then raise exception 'Organization admin permission required'; end if;
    if p_status not in('active','disabled','revoked') then raise exception 'Invalid device status'; end if;
    update public.privacy_gate_device_workspaces dw set status=p_status,updated_at=now() from public.privacy_gate_devices d
      where dw.organization_id=p_organization_id and dw.device_id=d.id and d.installation_hash=p_installation_hash;
    if not found then raise exception 'Managed device not found in this workspace'; end if;
end; $$;

grant execute on function public.privacy_gate_create_business_workspace(text,integer) to authenticated;
grant execute on function public.privacy_gate_accept_invitation(text,text,text,text,text) to authenticated;
grant execute on function public.privacy_gate_sync_team_device(uuid,text,text,text,text,integer) to authenticated;
grant execute on function public.privacy_gate_list_devices(uuid) to authenticated;
grant execute on function public.privacy_gate_set_device_status(uuid,text,text) to authenticated;
