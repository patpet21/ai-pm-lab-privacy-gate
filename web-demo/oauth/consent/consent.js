import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.111.0/+esm";

const supabase = createClient(
  "https://miihsvfvklwvwvvgeboh.supabase.co",
  "sb_publishable_b4Eb9zJqAba3m-cMCARx0Q_x0A-gICT"
);
const authorizationId = new URLSearchParams(location.search).get("authorization_id");
const status = document.querySelector("#status");
const details = document.querySelector("#details");
const login = document.querySelector("#login");
const emailInput = document.querySelector("#email");
const passwordInput = document.querySelector("#password");
const signInButton = document.querySelector("#sign-in");
const signUpButton = document.querySelector("#sign-up");

function setBusy(busy) {
  signInButton.disabled = busy;
  signUpButton.disabled = busy;
}

function credentials() {
  return {
    email: emailInput.value.trim(),
    password: passwordInput.value,
  };
}

async function loadConsent() {
  if (!authorizationId) {
    status.textContent = "Invalid request: authorization ID is missing.";
    return;
  }
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    status.textContent = "Sign in with the account used by your Privacy Gate desktop app.";
    login.hidden = false;
    details.hidden = true;
    return;
  }
  login.hidden = true;
  const { data, error } = await supabase.auth.oauth.getAuthorizationDetails(authorizationId);
  if (error || !data) {
    status.textContent = error?.message || "This authorization request is invalid or expired.";
    return;
  }
  if (!("authorization_id" in data)) {
    location.assign(data.redirect_url);
    return;
  }
  const clientName = data.client?.name || "ChatGPT / Claude AI client";
  document.querySelector("#client-name").textContent = clientName;
  document.querySelector("#title").textContent = `Authorize ${clientName}`;
  status.textContent = `Signed in as ${user.email}. Confirm that this is the account shown in Privacy Gate.`;
  details.hidden = false;
}

login.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  status.textContent = "Signing in…";
  try {
    const { error } = await supabase.auth.signInWithPassword(credentials());
    if (error) status.textContent = error.message;
    else await loadConsent();
  } catch (error) {
    status.textContent = error?.message || "Unable to sign in. Please try again.";
  } finally {
    setBusy(false);
  }
});

signUpButton.addEventListener("click", async () => {
  if (!login.reportValidity()) return;
  setBusy(true);
  status.textContent = "Creating your free MCP account…";
  try {
    const { data, error } = await supabase.auth.signUp(credentials());
    if (error) {
      status.textContent = error.message;
    } else if (!data.session) {
      status.textContent = "Account created, but no session was returned. Email confirmation must remain disabled in Privacy Gate Auth.";
    } else {
      await loadConsent();
    }
  } catch (error) {
    status.textContent = error?.message || "Unable to create the account. Please try again.";
  } finally {
    setBusy(false);
  }
});

document.querySelector("#approve").addEventListener("click", async () => {
  status.textContent = "Authorizing…";
  const { data, error } = await supabase.auth.oauth.approveAuthorization(authorizationId);
  if (error) status.textContent = error.message;
  else location.assign(data.redirect_url);
});

document.querySelector("#deny").addEventListener("click", async () => {
  const { data, error } = await supabase.auth.oauth.denyAuthorization(authorizationId);
  if (error) status.textContent = error.message;
  else location.assign(data.redirect_url);
});

loadConsent().catch((error) => {
  status.textContent = error?.message || "Unable to load the authorization request.";
});
