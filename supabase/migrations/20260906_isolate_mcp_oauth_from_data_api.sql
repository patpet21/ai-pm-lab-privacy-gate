-- PrivacyGate 0.5.0 release hardening
-- Keep Supabase OAuth/MCP tokens valid for the local MCP resource while
-- preventing those third-party OAuth sessions from using PrivacyGate Data API
-- tables or privileged RPCs directly.

create or replace function public.privacy_gate_is_direct_session()
returns boolean
language sql
stable
set search_path = ''
as $$
  select auth.uid() is not null
     and nullif(auth.jwt() ->> 'client_id', '') is null
     and coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) is false;
$$;

revoke all on function public.privacy_gate_is_direct_session() from public;
grant execute on function public.privacy_gate_is_direct_session() to authenticated;

create or replace function public.privacy_gate_require_direct_session()
returns void
language plpgsql
stable
set search_path = ''
as $$
begin
  if not public.privacy_gate_is_direct_session() then
    raise exception 'OAuth client sessions are not permitted for PrivacyGate data operations'
      using errcode = '42501';
  end if;
end;
$$;

revoke all on function public.privacy_gate_require_direct_session() from public;

-- One restrictive policy per application table. Existing user/org policies
-- remain unchanged and still decide which rows a direct PrivacyGate session
-- may access; this additional policy only rejects OAuth client JWTs.

create policy privacy_gate_direct_session_only
on public.privacy_gate_devices
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_profiles
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_entitlements
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_organizations
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_memberships
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_org_entitlements
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_policies
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_policy_versions
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_invitations
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

create policy privacy_gate_direct_session_only
on public.privacy_gate_device_workspaces
as restrictive
for all
to authenticated
using (public.privacy_gate_is_direct_session())
with check (public.privacy_gate_is_direct_session());

-- Central authorization helpers are also used by the remaining privileged
-- organization RPCs. Make them fail closed for OAuth client sessions.

create or replace function public.privacy_gate_has_org_role(p_organization_id uuid, p_roles text[])
returns boolean
language sql
stable
security definer
set search_path to 'public', 'auth'
as $$
select public.privacy_gate_is_direct_session()
   and exists(
     select 1
     from public.privacy_gate_memberships m
     where m.organization_id = p_organization_id
       and m.user_id = auth.uid()
       and m.status = 'active'
       and m.role = any(p_roles)
   );
$$;

create or replace function public.privacy_gate_is_org_member(p_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path to 'public', 'auth'
as $$
select public.privacy_gate_is_direct_session()
   and exists(
     select 1
     from public.privacy_gate_memberships m
     where m.organization_id = p_organization_id
       and m.user_id = auth.uid()
       and m.status = 'active'
   );
$$;

-- These three SECURITY DEFINER entry points do not route through the role
-- helpers above, so guard them explicitly at function entry.

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
set search_path to 'public', 'auth', 'extensions'
as $$
declare
  v_user uuid := auth.uid();
  v_inv public.privacy_gate_invitations%rowtype;
  v_membership uuid;
  v_seat_limit integer;
  v_active_count integer;
  v_policy_version integer;
  v_device uuid;
begin
  perform public.privacy_gate_require_direct_session();
  if v_user is null then raise exception 'Authentication required'; end if;
  if char_length(btrim(coalesce(p_code,''))) < 10 then raise exception 'Invalid invitation code'; end if;
  select * into v_inv from public.privacy_gate_invitations where token_hash=encode(digest(btrim(p_code),'sha256'),'hex') and status='pending' and expires_at>now() for update;
  if not found then raise exception 'Invitation is invalid, expired or already used'; end if;
  select seat_limit into v_seat_limit from public.privacy_gate_org_entitlements where organization_id=v_inv.organization_id and plan_code in('business','enterprise') and status in('trialing','active');
  if v_seat_limit is null then raise exception 'Organization entitlement is not active'; end if;
  select count(*) into v_active_count from public.privacy_gate_memberships where organization_id=v_inv.organization_id and status='active' and user_id<>v_user;
  if v_active_count>=v_seat_limit then raise exception 'No PrivacyGate seats are available for this organization'; end if;
  insert into public.privacy_gate_memberships(organization_id,user_id,role,status) values(v_inv.organization_id,v_user,v_inv.role,'active') on conflict(organization_id,user_id) do update set role=excluded.role,status='active' returning id into v_membership;
  update public.privacy_gate_invitations set status='used',used_by=v_user,used_at=now() where id=v_inv.id;
  select active_version into v_policy_version from public.privacy_gate_policies where organization_id=v_inv.organization_id and status='active';
  if exists(select 1 from public.privacy_gate_devices where installation_hash=p_installation_hash and user_id<>v_user) then raise exception 'This device identity is already bound to another account'; end if;
  insert into public.privacy_gate_devices(user_id,installation_hash,display_name,platform,app_version,status) values(v_user,p_installation_hash,coalesce(nullif(btrim(p_display_name),''),'This PC'),coalesce(p_platform,''),coalesce(p_app_version,''),'active') on conflict(installation_hash) do update set display_name=excluded.display_name,platform=excluded.platform,app_version=excluded.app_version returning id into v_device;
  insert into public.privacy_gate_device_workspaces(organization_id,membership_id,device_id,status,last_policy_version,last_policy_sync_at) values(v_inv.organization_id,v_membership,v_device,'active',v_policy_version,now()) on conflict(organization_id,device_id) do update set membership_id=excluded.membership_id,status='active',last_policy_version=excluded.last_policy_version,last_policy_sync_at=excluded.last_policy_sync_at,updated_at=now();
  update public.privacy_gate_devices set organization_id=coalesce(organization_id,v_inv.organization_id),membership_id=coalesce(membership_id,v_membership) where id=v_device;
  return v_inv.organization_id;
end;
$$;

create or replace function public.privacy_gate_create_business_workspace(
  p_name text,
  p_seat_limit integer default 5
)
returns uuid
language plpgsql
security definer
set search_path to 'public', 'auth', 'extensions'
as $$
declare
  v_user uuid := auth.uid();
  v_org uuid;
  v_policy uuid;
  v_name text := btrim(coalesce(p_name,''));
  v_seats integer := greatest(2,least(coalesce(p_seat_limit,5),100));
  v_default_policy jsonb;
begin
  perform public.privacy_gate_require_direct_session();
  if v_user is null then raise exception 'Authentication required'; end if;
  if char_length(v_name)<2 or char_length(v_name)>120 then raise exception 'Organization name must be between 2 and 120 characters'; end if;
  insert into public.privacy_gate_organizations(name,created_by) values(v_name,v_user) returning id into v_org;
  insert into public.privacy_gate_memberships(organization_id,user_id,role,status) values(v_org,v_user,'owner','active');
  insert into public.privacy_gate_org_entitlements(organization_id,plan_code,status,seat_limit,device_limit_per_member) values(v_org,'business','trialing',v_seats,2);
  insert into public.privacy_gate_policies(organization_id,name,active_version,created_by) values(v_org,'Company Privacy Policy',1,v_user) returning id into v_policy;
  v_default_policy:=jsonb_build_object('allowed_ai',jsonb_build_object('chatgpt',true,'claude',true,'other',false),'allowed_connectors',jsonb_build_object('gmail',true,'google_drive',true,'clickup',true,'asana',true,'trello',true,'notion',false,'monday',false,'jira',false),'protection_rules',jsonb_build_object('US_SSN','required_protect','US_BANK_NUMBER','required_protect','US_ROUTING_NUMBER','required_protect','CREDIT_CARD','required_protect','EMAIL_ADDRESS','default_protect','PHONE_NUMBER','default_protect','PERSON','user_choice','STREET_ADDRESS','user_choice','LOCATION','user_choice','MONEY_AMOUNT','allow','CUSTOMER_ID','default_protect','EMPLOYEE_ID','default_protect'));
  insert into public.privacy_gate_policy_versions(policy_id,organization_id,version,policy_json,policy_sha256,created_by) values(v_policy,v_org,1,v_default_policy,encode(digest(v_default_policy::text,'sha256'),'hex'),v_user);
  return v_org;
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
set search_path to 'public', 'auth'
as $$
declare
  v_user uuid := auth.uid();
  v_membership uuid;
  v_device uuid;
  v_device_limit integer;
  v_bound_devices integer;
begin
  perform public.privacy_gate_require_direct_session();
  if v_user is null then raise exception 'Authentication required'; end if;
  select id into v_membership from public.privacy_gate_memberships where organization_id=p_organization_id and user_id=v_user and status='active';
  if v_membership is null then raise exception 'Active organization membership required'; end if;
  if exists(select 1 from public.privacy_gate_devices where installation_hash=p_installation_hash and user_id<>v_user) then raise exception 'This device identity is already bound to another account'; end if;
  insert into public.privacy_gate_devices(user_id,installation_hash,display_name,platform,app_version,status) values(v_user,p_installation_hash,coalesce(nullif(btrim(p_display_name),''),'This PC'),coalesce(p_platform,''),coalesce(p_app_version,''),'active') on conflict(installation_hash) do update set display_name=excluded.display_name,platform=excluded.platform,app_version=excluded.app_version returning id into v_device;
  select device_limit_per_member into v_device_limit from public.privacy_gate_org_entitlements where organization_id=p_organization_id and status in('trialing','active');
  if v_device_limit is not null then select count(*) into v_bound_devices from public.privacy_gate_device_workspaces dw where dw.organization_id=p_organization_id and dw.membership_id=v_membership and dw.device_id<>v_device and dw.status='active'; if v_bound_devices>=v_device_limit then raise exception 'Device limit reached for this workspace member'; end if; end if;
  insert into public.privacy_gate_device_workspaces(organization_id,membership_id,device_id,status,last_policy_version,last_policy_sync_at) values(p_organization_id,v_membership,v_device,'active',p_policy_version,now()) on conflict(organization_id,device_id) do update set membership_id=excluded.membership_id,last_policy_version=excluded.last_policy_version,last_policy_sync_at=excluded.last_policy_sync_at,updated_at=now();
  update public.privacy_gate_devices set organization_id=coalesce(organization_id,p_organization_id),membership_id=coalesce(membership_id,v_membership) where id=v_device;
end;
$$;
