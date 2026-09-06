import os, sys, tempfile, json, base64, hmac, hashlib
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'src'))
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_accounts import GmailAccountRegistry
from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import GmailAddonTransport
from ai_pm_lab_privacy_gate.infrastructure.security.secret_store import MemorySecretStore
endpoint='https://script.google.com/macros/s/test/exec'
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)
    (path/'gmail_addon.json').write_text(json.dumps({'channel':'legacy-channel-12345678','paired':True,'endpoint':endpoint,'readonly_channel':'obsolete'}))
    store=MemorySecretStore()
    a=GmailAccountRegistry(path,store)
    first=a.active_id
    assert a.channel(first)=='legacy-channel-12345678'
    assert 'legacy-channel' not in a.path.read_text()
    second=a.add('Work',endpoint)
    assert a.active_id==first and a.channel(first)!=a.channel(second)
    b=GmailAccountRegistry(path,store)
    a.update(second,paired=True)
    b.select(second)
    a.update(first,paired=True)
    assert b.active_id==second and len(b.accounts())==2
    one=GmailAddonTransport(path,account_id=first,registry=a)
    two=GmailAddonTransport(path,account_id=second,registry=b)
    payload=base64.urlsafe_b64encode(json.dumps({'body':'Selected email','subject':'Test'}).encode()).decode().rstrip('=')
    sig=base64.urlsafe_b64encode(hmac.new(one.channel.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip('=')
    response={'ready':True,'payload_b64':payload,'signature':sig}
    one._post=lambda *_:response
    two._post=lambda *_:response
    assert one.poll().body=='Selected email'
    try: two.poll()
    except RuntimeError: pass
    else: raise AssertionError('Cross-account signature accepted')
    a.remove(second)
    assert a.active_id==first and a.channel(first)=='legacy-channel-12345678'
print('PASS migration, secret storage, multiple accounts, stale writers, HMAC isolation, removal')
from PySide6.QtWidgets import QApplication,QMainWindow
from types import SimpleNamespace
from ai_pm_lab_privacy_gate.ui.gmail_addon_accounts_ui import GmailAccountsDialog, release_settings
from ai_pm_lab_privacy_gate.ui.gmail_addon_import import GmailImportDialog
app=QApplication.instance() or QApplication([])
from ai_pm_lab_privacy_gate.ui.fonts import install_app_font
from ai_pm_lab_privacy_gate.ui.styles import APP_STYLE
install_app_font(app)
app.setStyleSheet(APP_STYLE)
with tempfile.TemporaryDirectory() as directory:
    window=QMainWindow()
    window.apps_hub_page=SimpleNamespace(service=SimpleNamespace(data_dir=Path(directory)))
    registry=GmailAccountRegistry(directory)
    first=registry.add('Personal Gmail',endpoint)
    registry.update(first,paired=True)
    second=registry.add('Work Gmail',endpoint)
    registry.update(second,paired=True)
    accounts=GmailAccountsDialog(window)
    accounts.show()
    app.processEvents()
    accounts.grab().save(str(Path(tempfile.gettempdir())/'privacygate-gmail-accounts.png'))
    receiver=GmailImportDialog(window)
    receiver.timer.stop()
    assert receiver.accounts.count()==2
    receiver.accounts.setCurrentIndex(1)
    assert receiver.transport.account_id==second
    assert not receiver.use.isEnabled()
    receiver.show()
    app.processEvents()
    receiver.grab().save(str(Path(tempfile.gettempdir())/'privacygate-gmail-protect.png'))
    receiver.reject()
    accounts.reject()
assert release_settings()==('','')
scopes=json.loads((repo/'integrations/gmail-addon/appsscript.json').read_text())['oauthScopes']
assert 'https://www.googleapis.com/auth/gmail.addons.current.message.action' in scopes
assert not any('readonly' in s or s.endswith('/mail.google.com/') for s in scopes)
print('PASS real Qt dialogs, account selection, unpublished installation gate, action-only manifest')
if '--full-app' in sys.argv:
    os.environ['PRIVACY_GATE_DATA_DIR']=tempfile.mkdtemp(prefix='pg-action-smoke-')
    from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
    from ai_pm_lab_privacy_gate.ui.main_window import MainWindow
    from ai_pm_lab_privacy_gate.ui.gmail_addon_import import _adopt_addon_component, _data_dir
    from ai_pm_lab_privacy_gate.infrastructure.connectors.gmail_addon_transport import GmailAddonMessage
    service=PrivacyGateService()
    window=MainWindow(service=service)
    registry=GmailAccountRegistry(_data_dir(window))
    key=registry.add('Smoke account',endpoint)
    registry.update(key,paired=True)
    transport=GmailAddonTransport(registry.data_dir,account_id=key)
    message=GmailAddonMessage('1','1','Selected email','sender@example.com','recipient@example.com','2026-09-06','Contact jane.smith@example.com',())
    _adopt_addon_component(window,message,'body',-1,transport)
    page=window.protection_page
    assert 'jane.smith@example.com' in page.text_input.toPlainText()
    assert page._external_source_metadata['account_id']==key
    document=service.document_from_text(page.text_input.toPlainText())
    findings=service.analyze(document,page._current_profile())
    assert findings
    page._analysis_ready((document, findings))
    page._redesign_protect_button.click()
    app.processEvents()
    assert page.current_result
    print('PASS actual MainWindow Gmail import, account provenance, Scan and Protect',flush=True)
    os._exit(0)
