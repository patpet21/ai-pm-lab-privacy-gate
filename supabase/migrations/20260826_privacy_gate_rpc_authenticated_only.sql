-- SECURITY DEFINER RPCs are exposed by PostgREST only to signed-in PrivacyGate users.
-- Function bodies still enforce organization membership and Owner/Admin roles.
revoke execute on function public.privacy_gate_accept_invitation(text,text,text,text,text) from public, anon;
revoke execute on function public.privacy_gate_create_business_workspace(text,integer) from public, anon;
revoke execute on function public.privacy_gate_create_invitation(uuid,text,integer) from public, anon;
revoke execute on function public.privacy_gate_has_org_role(uuid,text[]) from public, anon;
revoke execute on function public.privacy_gate_is_org_member(uuid) from public, anon;
revoke execute on function public.privacy_gate_list_devices(uuid) from public, anon;
revoke execute on function public.privacy_gate_list_members(uuid) from public, anon;
revoke execute on function public.privacy_gate_publish_policy(uuid,jsonb,text) from public, anon;
revoke execute on function public.privacy_gate_set_device_status(uuid,text,text) from public, anon;
revoke execute on function public.privacy_gate_set_member_role(uuid,uuid,text) from public, anon;
revoke execute on function public.privacy_gate_set_member_status(uuid,uuid,text) from public, anon;
revoke execute on function public.privacy_gate_sync_team_device(uuid,text,text,text,text,integer) from public, anon;

grant execute on function public.privacy_gate_accept_invitation(text,text,text,text,text) to authenticated;
grant execute on function public.privacy_gate_create_business_workspace(text,integer) to authenticated;
grant execute on function public.privacy_gate_create_invitation(uuid,text,integer) to authenticated;
grant execute on function public.privacy_gate_has_org_role(uuid,text[]) to authenticated;
grant execute on function public.privacy_gate_is_org_member(uuid) to authenticated;
grant execute on function public.privacy_gate_list_devices(uuid) to authenticated;
grant execute on function public.privacy_gate_list_members(uuid) to authenticated;
grant execute on function public.privacy_gate_publish_policy(uuid,jsonb,text) to authenticated;
grant execute on function public.privacy_gate_set_device_status(uuid,text,text) to authenticated;
grant execute on function public.privacy_gate_set_member_role(uuid,uuid,text) to authenticated;
grant execute on function public.privacy_gate_set_member_status(uuid,uuid,text) to authenticated;
grant execute on function public.privacy_gate_sync_team_device(uuid,text,text,text,text,integer) to authenticated;
