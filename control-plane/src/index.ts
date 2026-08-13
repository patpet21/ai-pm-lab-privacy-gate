interface Env {
  DB: D1Database;
  BASE_URL: string;
  MCP_DOMAIN: string;
  SUPABASE_ISSUER: string;
  CF_ACCOUNT_ID: string;
  CF_ZONE_ID: string;
  CF_API_TOKEN: string;
  JWT_PRIVATE_JWK: string;
  JWT_PUBLIC_JWK: string;
  PROVISIONING_FINGERPRINT_SALT: string;
}

type Json = Record<string, unknown>;
const encoder = new TextEncoder();

function json(data: Json, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(data), {status, headers:{"content-type":"application/json","cache-control":"no-store",...headers}});
}

function html(body: string, status = 200): Response {
  return new Response(body, {status, headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","content-security-policy":"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'","x-content-type-options":"nosniff"}});
}

function b64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function fromB64url(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(normalized + "=".repeat((4 - normalized.length % 4) % 4));
  return Uint8Array.from(binary, character => character.charCodeAt(0));
}

function randomToken(bytes = 32): string {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return b64url(value);
}

async function sha256(value: string | Uint8Array): Promise<string> {
  const bytes = typeof value === "string" ? encoder.encode(value) : value;
  return b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[character] ?? character);
}

function installationFromResource(resource: string, domain: string): string | null {
  try {
    const url = new URL(resource);
    const match = new RegExp(`^mcp-pg-([a-f0-9]{32})\\.${domain.replace(".", "\\.")}$`).exec(url.hostname);
    const supportedPath = url.pathname === "/" || url.pathname === "/mcp";
    return url.protocol === "https:" && supportedPath ? match?.[1] ?? null : null;
  } catch { return null; }
}

async function protectedResourceMetadata(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const resource = `https://${url.hostname}/mcp`;
  const installationId = installationFromResource(resource, env.MCP_DOMAIN);
  if (!installationId) return json({error:"not_found"},404);
  const device: any = await env.DB.prepare(
    "SELECT status FROM devices WHERE installation_id = ?"
  ).bind(installationId).first();
  if (!device || device.status !== "active") return json({error:"not_found"},404);
  return json({
    resource,
    authorization_servers:[env.SUPABASE_ISSUER],
    scopes_supported:["email"],
    bearer_methods_supported:["header"]
  },200,{"cache-control":"public, max-age=30","access-control-allow-origin":"*"});
}

async function cf(env: Env, path: string, init: RequestInit): Promise<any> {
  const response = await fetch(`https://api.cloudflare.com/client/v4${path}`, {...init,headers:{authorization:`Bearer ${env.CF_API_TOKEN}`,"content-type":"application/json",...(init.headers ?? {})}});
  const payload: any = await response.json();
  if (!response.ok || !payload.success) throw new Error(`Cloudflare API request failed (${response.status})`);
  return payload.result;
}

async function provisionTunnel(env: Env, installationId: string): Promise<{tunnelId:string;hostname:string;token:string}> {
  const hostname = `mcp-pg-${installationId}.${env.MCP_DOMAIN}`;
  const created = await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel`, {method:"POST",body:JSON.stringify({name:`privacy-gate-${installationId}`,config_src:"cloudflare"})});
  const tunnelId = String(created.id);
  try {
    await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}/configurations`, {method:"PUT",body:JSON.stringify({config:{ingress:[{hostname,service:"http://127.0.0.1:8766",originRequest:{httpHostHeader:"127.0.0.1"}},{service:"http_status:404"}]}})});
    const existing = await cf(env, `/zones/${env.CF_ZONE_ID}/dns_records?type=CNAME&name=${encodeURIComponent(hostname)}`, {method:"GET"});
    const dnsBody = JSON.stringify({type:"CNAME",proxied:true,name:hostname,content:`${tunnelId}.cfargotunnel.com`});
    if (Array.isArray(existing) && existing.length) {
      await cf(env, `/zones/${env.CF_ZONE_ID}/dns_records/${existing[0].id}`, {method:"PUT",body:dnsBody});
    } else {
      await cf(env, `/zones/${env.CF_ZONE_ID}/dns_records`, {method:"POST",body:dnsBody});
    }
    const token = created.token || await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}/token`, {method:"GET"});
    return {tunnelId,hostname,token:String(token)};
  } catch (error) {
    await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}`, {method:"DELETE"}).catch(()=>undefined);
    throw error;
  }
}

async function tunnelToken(env: Env, tunnelId: string): Promise<string> {
  return String(await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}/token`, {method:"GET"}));
}

async function removeTunnelResources(env: Env, tunnelId: string, hostname: string): Promise<void> {
  const records = await cf(env, `/zones/${env.CF_ZONE_ID}/dns_records?type=CNAME&name=${encodeURIComponent(hostname)}`, {method:"GET"}).catch(()=>[]);
  for (const record of Array.isArray(records) ? records : []) {
    await cf(env, `/zones/${env.CF_ZONE_ID}/dns_records/${record.id}`, {method:"DELETE"}).catch(()=>undefined);
  }
  await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}/connections`, {method:"DELETE"}).catch(()=>undefined);
  await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${tunnelId}`, {method:"DELETE"}).catch(()=>undefined);
}

async function startEnrollment(request: Request, env: Env): Promise<Response> {
  const body: any = await request.json();
  if (!/^[a-f0-9]{32}$/.test(body.installation_id ?? "")) return json({error:"invalid_installation_id"},400);
  if (body.device_public_jwk?.kty !== "EC" || body.device_public_jwk?.crv !== "P-256") return json({error:"invalid_device_key"},400);
  const existingDevice: any = await env.DB.prepare("SELECT status, device_public_jwk FROM devices WHERE installation_id = ?").bind(body.installation_id).first();
  if (existingDevice?.status === "active") return json({error:"device_already_exists"},409);
  if (existingDevice && JSON.stringify(JSON.parse(existingDevice.device_public_jwk)) !== JSON.stringify(body.device_public_jwk)) {
    return json({error:"installation_identity_mismatch"},409);
  }
  const sessionId = crypto.randomUUID(), sessionSecret = randomToken(), activationCode = randomToken(8).slice(0,10).toUpperCase(), now = Math.floor(Date.now()/1000);
  const clientIp = request.headers.get("cf-connecting-ip") ?? request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const clientFingerprint = await sha256(`${clientIp}\n${env.PROVISIONING_FINGERPRINT_SALT}`);
  const clientRecent: any = await env.DB.prepare("SELECT COUNT(*) AS count FROM enrollment_sessions WHERE client_fingerprint = ? AND created_at > ?").bind(clientFingerprint,now-86400).first();
  const globalRecent: any = await env.DB.prepare("SELECT COUNT(*) AS count FROM enrollment_sessions WHERE created_at > ?").bind(now-3600).first();
  const knownDeviceRecovery = existingDevice?.status === "revoked";
  if (!knownDeviceRecovery && (Number(clientRecent?.count ?? 0) >= 3 || Number(globalRecent?.count ?? 0) >= 100)) return json({error:"enrollment_rate_limited"},429,{"retry-after":"3600"});
  await env.DB.prepare("INSERT INTO enrollment_sessions(session_id,installation_id,session_secret_hash,activation_code_hash,device_public_jwk,state,expires_at,created_at,client_fingerprint) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)").bind(sessionId,body.installation_id,await sha256(sessionSecret),await sha256(activationCode),JSON.stringify(body.device_public_jwk),now+1800,now,clientFingerprint).run();
  return json({session_id:sessionId,session_secret:sessionSecret,activation_url:`${env.BASE_URL}/activate?session=${encodeURIComponent(sessionId)}&code=${encodeURIComponent(activationCode)}`},201);
}

async function activationPage(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url), session = url.searchParams.get("session") ?? "", code = url.searchParams.get("code") ?? "";
  const row: any = await env.DB.prepare("SELECT installation_id, state, expires_at FROM enrollment_sessions WHERE session_id = ?").bind(session).first();
  if (!row || row.expires_at < Date.now()/1000) return html("<h1>Activation expired</h1>",410);
  return html(`<!doctype html><meta name="viewport" content="width=device-width"><title>Activate Privacy Gate</title><style>body{font:16px system-ui;max-width:620px;margin:60px auto;padding:24px;color:#08243b}button{background:#078f98;color:white;border:0;padding:14px 20px;border-radius:9px;font-weight:700}input{display:none}</style><h1>Activate stable AI connection</h1><p>Installation <strong>${escapeHtml(row.installation_id.slice(0,8).toUpperCase())}</strong></p><p>This creates one stable, metadata-only connection for this Privacy Gate installation. Only documents already saved in the Protected Library can be shared. Original documents and restore mappings remain local.</p><form method="post" action="/activate"><input type="hidden" name="session" value="${escapeHtml(session)}"><input type="hidden" name="code" value="${escapeHtml(code)}"><button>Activate this device</button></form>`);
}

async function approveActivation(request: Request, env: Env): Promise<Response> {
  const form = await request.formData(), session = String(form.get("session") ?? ""), code = String(form.get("code") ?? "");
  const row: any = await env.DB.prepare("SELECT activation_code_hash, expires_at FROM enrollment_sessions WHERE session_id = ?").bind(session).first();
  if (!row || row.expires_at < Date.now()/1000 || row.activation_code_hash !== await sha256(code)) return html("<h1>Activation request is invalid or expired</h1>",400);
  await env.DB.prepare("UPDATE enrollment_sessions SET state = 'approved' WHERE session_id = ?").bind(session).run();
  return html("<h1>Device approved</h1><p>Return to Privacy Gate and select <strong>Check activation</strong>.</p>");
}

async function pollEnrollment(request: Request, env: Env, sessionId: string): Promise<Response> {
  const token = request.headers.get("authorization")?.replace(/^Bearer /,"") ?? "";
  const row: any = await env.DB.prepare("SELECT * FROM enrollment_sessions WHERE session_id = ?").bind(sessionId).first();
  if (!row || row.session_secret_hash !== await sha256(token)) return json({error:"unauthorized"},401);
  if (row.expires_at < Date.now()/1000) return json({state:"expired"},410);
  if (row.state === "pending") return json({state:"pending"});
  if (row.state === "ready") {
    const device:any = await env.DB.prepare("SELECT * FROM devices WHERE installation_id = ? AND status = 'active'").bind(row.installation_id).first();
    if (!device) return json({state:"revoked"},410);
    return json({state:"ready",configuration:{installation_id:row.installation_id,tunnel_id:device.tunnel_id,hostname:device.hostname,oauth_issuer:env.SUPABASE_ISSUER,oauth_jwks_url:`${env.SUPABASE_ISSUER}/.well-known/jwks.json`,credential_version:device.credential_version,state:"ready"},tunnel_token:await tunnelToken(env,device.tunnel_id)});
  }
  if (row.state !== "approved") return json({state:row.state});
  const lock = await env.DB.prepare("UPDATE enrollment_sessions SET state = 'provisioning' WHERE session_id = ? AND state = 'approved'").bind(sessionId).run();
  if (!lock.meta.changes) return json({state:"provisioning"});
  try {
    const provisioned = await provisionTunnel(env,row.installation_id), now = Math.floor(Date.now()/1000);
    const existingDevice: any = await env.DB.prepare("SELECT status, credential_version FROM devices WHERE installation_id = ?").bind(row.installation_id).first();
    const credentialVersion = existingDevice ? Number(existingDevice.credential_version) + 1 : 1;
    const deviceWrite = existingDevice
      ? env.DB.prepare("UPDATE devices SET device_public_jwk = ?, tunnel_id = ?, hostname = ?, credential_version = ?, status = 'active', last_seen_at = ? WHERE installation_id = ?").bind(row.device_public_jwk,provisioned.tunnelId,provisioned.hostname,credentialVersion,now,row.installation_id)
      : env.DB.prepare("INSERT INTO devices(installation_id,device_public_jwk,tunnel_id,hostname,created_at,last_seen_at) VALUES (?, ?, ?, ?, ?, ?)").bind(row.installation_id,row.device_public_jwk,provisioned.tunnelId,provisioned.hostname,now,now);
    await env.DB.batch([deviceWrite,env.DB.prepare("UPDATE enrollment_sessions SET state = 'ready' WHERE session_id = ?").bind(sessionId)]);
    return json({state:"ready",configuration:{installation_id:row.installation_id,tunnel_id:provisioned.tunnelId,hostname:provisioned.hostname,oauth_issuer:env.SUPABASE_ISSUER,oauth_jwks_url:`${env.SUPABASE_ISSUER}/.well-known/jwks.json`,credential_version:credentialVersion,state:"ready"},tunnel_token:provisioned.token});
  } catch { await env.DB.prepare("UPDATE enrollment_sessions SET state = 'approved' WHERE session_id = ?").bind(sessionId).run(); return json({error:"provisioning_failed"},502); }
}

async function deviceLifecycle(request: Request, env: Env, action: "rotate"|"revoke"): Promise<Response> {
  const body = new Uint8Array(await request.arrayBuffer()), installationId = await verifyDevice(request,env,body);
  if (!installationId) return json({error:"unauthorized_device"},401);
  const device:any = await env.DB.prepare("SELECT * FROM devices WHERE installation_id = ? AND status = 'active'").bind(installationId).first();
  if (!device) return json({error:"device_not_found"},404);
  if (action === "revoke") {
    await env.DB.prepare("UPDATE devices SET status = 'revoked' WHERE installation_id = ?").bind(installationId).run();
    await env.DB.prepare("UPDATE pairings SET status = 'revoked', auth_code_delivery = NULL WHERE installation_id = ? AND status NOT IN ('consumed','expired')").bind(installationId).run();
    await removeTunnelResources(env,device.tunnel_id,device.hostname);
    return json({state:"revoked"});
  }
  await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${device.tunnel_id}/connections`, {method:"DELETE"}).catch(()=>undefined);
  await cf(env, `/accounts/${env.CF_ACCOUNT_ID}/cfd_tunnel/${device.tunnel_id}`, {method:"DELETE"});
  const replacement = await provisionTunnel(env,installationId);
  await env.DB.prepare("UPDATE devices SET tunnel_id = ?, hostname = ?, credential_version = credential_version + 1, last_seen_at = ? WHERE installation_id = ?").bind(replacement.tunnelId,replacement.hostname,Math.floor(Date.now()/1000),installationId).run();
  return json({state:"ready",configuration:{installation_id:installationId,tunnel_id:replacement.tunnelId,hostname:replacement.hostname,oauth_issuer:env.SUPABASE_ISSUER,oauth_jwks_url:`${env.SUPABASE_ISSUER}/.well-known/jwks.json`,credential_version:Number(device.credential_version)+1,state:"ready"},tunnel_token:replacement.token});
}

async function verifyDevice(request: Request, env: Env, body: Uint8Array): Promise<string|null> {
  const installationId=request.headers.get("x-pg-installation")??"", timestamp=request.headers.get("x-pg-timestamp")??"", nonce=request.headers.get("x-pg-nonce")??"", signature=request.headers.get("x-pg-signature")??"";
  if (!installationId || !timestamp || !nonce || !signature || Math.abs(Date.now()/1000-Number(timestamp))>300) return null;
  const device:any=await env.DB.prepare("SELECT device_public_jwk FROM devices WHERE installation_id = ? AND status = 'active'").bind(installationId).first();
  if (!device) return null;
  const canonical=`${timestamp}\n${nonce}\n${request.method.toUpperCase()}\n${new URL(request.url).pathname}\n${await sha256(body)}`;
  const key=await crypto.subtle.importKey("jwk",JSON.parse(device.device_public_jwk),{name:"ECDSA",namedCurve:"P-256"},false,["verify"]);
  if (!await crypto.subtle.verify({name:"ECDSA",hash:"SHA-256"},key,fromB64url(signature),encoder.encode(canonical))) return null;
  const inserted=await env.DB.prepare("INSERT OR IGNORE INTO request_nonces VALUES (?, ?, ?)").bind(installationId,nonce,Math.floor(Date.now()/1000)+600).run();
  return inserted.meta.changes ? installationId : null;
}

async function clientRedirectAllowed(clientId:string, redirectUri:string):Promise<boolean>{
  try{const url=new URL(clientId);if(url.protocol!=="https:"||!["chatgpt.com","claude.ai","anthropic.com"].some(domain=>url.hostname===domain||url.hostname.endsWith(`.${domain}`)))return false;const response=await fetch(url.toString(),{headers:{accept:"application/json"}});if(!response.ok)return false;const metadata:any=await response.json();return metadata.client_id===clientId&&Array.isArray(metadata.redirect_uris)&&metadata.redirect_uris.includes(redirectUri);}catch{return false;}
}

async function authorize(request:Request,env:Env):Promise<Response>{
  const url=new URL(request.url),clientId=url.searchParams.get("client_id")??"",redirectUri=url.searchParams.get("redirect_uri")??"",resource=url.searchParams.get("resource")??"",codeChallenge=url.searchParams.get("code_challenge")??"",state=url.searchParams.get("state")??"",scope=url.searchParams.get("scope")||"protected:read",installationId=installationFromResource(resource,env.MCP_DOMAIN);
  if(url.searchParams.get("response_type")!=="code"||url.searchParams.get("code_challenge_method")!=="S256"||!installationId||!codeChallenge)return json({error:"invalid_request"},400);
  const device:any=await env.DB.prepare("SELECT status FROM devices WHERE installation_id=?").bind(installationId).first();
  if(!device||device.status!=="active")return json({error:"invalid_resource"},400);
  if(!await clientRedirectAllowed(clientId,redirectUri))return json({error:"invalid_client"},400);
  const pairingId=crypto.randomUUID(),browserSecret=randomToken(),now=Math.floor(Date.now()/1000);
  const unusedCodeHash=await sha256(randomToken());
  await env.DB.prepare("INSERT INTO pairings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)").bind(pairingId,installationId,unusedCodeHash,await sha256(browserSecret),clientId,redirectUri,state,resource,scope,codeChallenge,now+600,now).run();
  return html(`<!doctype html><meta name="viewport" content="width=device-width"><title>Authorize Privacy Gate</title><style>:root{color-scheme:light}body{font:16px system-ui;max-width:620px;margin:60px auto;padding:24px;color:#08243b;background:#f4f7f8}.card{background:white;border:1px solid #d8e2e7;border-radius:18px;padding:32px;box-shadow:0 18px 55px rgba(8,36,59,.12)}.badge{display:inline-block;padding:7px 10px;border-radius:999px;background:#def3ee;color:#087064;font-weight:800;font-size:12px}button{width:100%;background:#078f98;color:white;border:0;padding:15px 20px;border-radius:9px;font-weight:800;font-size:15px;cursor:pointer}small{display:block;color:#607587;line-height:1.55;margin-top:18px}</style><div class="card"><span class="badge">PROTECTED LIBRARY ONLY</span><h1>Authorize AI access</h1><p>Allow this AI client to read documents you saved in Privacy Gate's Protected Library on device <strong>${escapeHtml(installationId.slice(0,8).toUpperCase())}</strong>.</p><p>Original documents, reversible mappings and restore keys are never available through this connection.</p><form method="post" action="/authorize/confirm"><input type="hidden" name="pairing_id" value="${escapeHtml(pairingId)}"><input type="hidden" name="browser_secret" value="${escapeHtml(browserSecret)}"><button type="submit">Authorize protected files</button></form><small>This permission is read-only and can be stopped or revoked from Privacy Gate. No AI PM LAB account is required.</small></div>`);
}

async function confirmAuthorization(request:Request,env:Env):Promise<Response>{
  const form=await request.formData(),pairingId=String(form.get("pairing_id")??""),browserSecret=String(form.get("browser_secret")??"");
  const row:any=await env.DB.prepare("SELECT * FROM pairings WHERE pairing_id=? AND status='pending'").bind(pairingId).first();
  if(!row||row.browser_secret_hash!==await sha256(browserSecret)||row.expires_at<Date.now()/1000)return html("<h1>Authorization request expired</h1><p>Return to ChatGPT or Claude and try connecting again.</p>",400);
  const authCode=randomToken();
  await env.DB.prepare("UPDATE pairings SET status='delivered',auth_code_hash=?,auth_code_delivery=NULL WHERE pairing_id=?").bind(await sha256(authCode),pairingId).run();
  const redirect=new URL(row.redirect_uri);redirect.searchParams.set("code",authCode);if(row.state_parameter)redirect.searchParams.set("state",row.state_parameter);
  return Response.redirect(redirect.toString(),302);
}

async function signJwt(env:Env,claims:Json):Promise<string>{
  const privateJwk=JSON.parse(env.JWT_PRIVATE_JWK),publicJwk=JSON.parse(env.JWT_PUBLIC_JWK),header=b64url(encoder.encode(JSON.stringify({alg:"ES256",typ:"JWT",kid:publicJwk.kid}))),payload=b64url(encoder.encode(JSON.stringify(claims))),key=await crypto.subtle.importKey("jwk",privateJwk,{name:"ECDSA",namedCurve:"P-256"},false,["sign"]),signature=new Uint8Array(await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},key,encoder.encode(`${header}.${payload}`)));
  return `${header}.${payload}.${b64url(signature)}`;
}

async function token(request:Request,env:Env):Promise<Response>{
  const form=await request.formData();if(form.get("grant_type")!=="authorization_code")return json({error:"unsupported_grant_type"},400);
  const code=String(form.get("code")??""),verifier=String(form.get("code_verifier")??""),row:any=await env.DB.prepare("SELECT * FROM pairings WHERE auth_code_hash=? AND status='delivered'").bind(await sha256(code)).first();
  const requestedResource=form.get("resource");
  if(!row||row.expires_at<Date.now()/1000||row.client_id!==form.get("client_id")||row.redirect_uri!==form.get("redirect_uri")||(requestedResource&&row.resource!==requestedResource)||await sha256(verifier)!==row.code_challenge)return json({error:"invalid_grant"},400);
  await env.DB.prepare("UPDATE pairings SET status='consumed' WHERE pairing_id=?").bind(row.pairing_id).run();const now=Math.floor(Date.now()/1000);
  return json({access_token:await signJwt(env,{iss:env.BASE_URL,sub:row.installation_id,aud:row.resource,scope:row.scope,iat:now,exp:now+600,jti:crypto.randomUUID()}),token_type:"Bearer",expires_in:600,scope:row.scope});
}

export default {async fetch(request:Request,env:Env):Promise<Response>{
  const url=new URL(request.url);
  try{
    if(request.method==="GET"&&url.pathname.startsWith("/.well-known/oauth-protected-resource"))return protectedResourceMetadata(request,env);
    if(request.method==="GET"&&url.pathname==="/health")return json({status:"ok",content_storage:false});
    if(request.method==="GET"&&url.pathname==="/.well-known/oauth-authorization-server")return json({issuer:env.BASE_URL,authorization_endpoint:`${env.BASE_URL}/authorize`,token_endpoint:`${env.BASE_URL}/token`,jwks_uri:`${env.BASE_URL}/.well-known/jwks.json`,client_id_metadata_document_supported:true,response_types_supported:["code"],grant_types_supported:["authorization_code"],token_endpoint_auth_methods_supported:["none"],code_challenge_methods_supported:["S256"],scopes_supported:["protected:metadata","protected:read"]});
    if(request.method==="GET"&&url.pathname==="/.well-known/jwks.json")return json({keys:[JSON.parse(env.JWT_PUBLIC_JWK)]},200,{"cache-control":"public, max-age=300"});
    if(request.method==="POST"&&url.pathname==="/v1/enrollments")return startEnrollment(request,env);
    const enrollment=/^\/v1\/enrollments\/([a-f0-9-]+)$/.exec(url.pathname);if(request.method==="GET"&&enrollment)return pollEnrollment(request,env,enrollment[1]);
    if(request.method==="GET"&&url.pathname==="/activate")return activationPage(request,env);if(request.method==="POST"&&url.pathname==="/activate")return approveActivation(request,env);
    if(request.method==="GET"&&url.pathname==="/authorize")return authorize(request,env);if(request.method==="POST"&&url.pathname==="/authorize/confirm")return confirmAuthorization(request,env);if(request.method==="POST"&&url.pathname==="/token")return token(request,env);
    if(request.method==="POST"&&url.pathname==="/v1/device/rotate")return deviceLifecycle(request,env,"rotate");
    if(request.method==="POST"&&url.pathname==="/v1/device/revoke")return deviceLifecycle(request,env,"revoke");
    return json({error:"not_found"},404);
  }catch{return json({error:"internal_error"},500);}
}};
