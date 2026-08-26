from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ai_pm_lab_privacy_gate.infrastructure.policy.workspace_context import WorkspaceContextStore
from ai_pm_lab_privacy_gate.ui.provider_logos import ProviderLogoLoader
from ai_pm_lab_privacy_gate.ui.team_page import TeamPage

_INSTALLED = False
NAVY="#062B4F"; TEAL="#0B7180"; GREEN="#23824B"; RED="#A23A3A"; MUTED="#61798A"; BORDER="#DCE5EA"; SOFT="#F7FAFC"
PROVIDERS=(("gmail","Gmail"),("google_drive","Google Drive"),("asana","Asana"),("clickup","ClickUp"),("trello","Trello"),("notion","Notion"),("monday","monday.com"),("jira","Jira"))
AI_PROVIDERS=(("chatgpt","ChatGPT"),("claude","Claude"),("gemini","Gemini"))


def _card():
    frame=QFrame(); frame.setStyleSheet(f"QFrame{{background:#FFFFFF;border:1px solid {BORDER};border-radius:12px;}}"); return frame

def _title(text,size=14):
    label=QLabel(text); label.setStyleSheet(f"color:{NAVY};font-size:{size}px;font-weight:900;"); return label

def _muted(text=""):
    label=QLabel(text); label.setWordWrap(True); label.setStyleSheet(f"color:{MUTED};font-size:9px;"); return label

def _find_layout_containing(root_layout,widget):
    for index in range(root_layout.count()):
        item=root_layout.itemAt(index); child_layout=item.layout()
        if child_layout is not None:
            for child_index in range(child_layout.count()):
                if child_layout.itemAt(child_index).widget() is widget: return child_layout
            nested=_find_layout_containing(child_layout,widget)
            if nested is not None: return nested
    return None


class WorkspaceBindingsDialog(QDialog):
    def __init__(self,*,provider,account_id,account_label,context_store,parent=None):
        super().__init__(parent); self.provider=provider; self.account_id=account_id; self.context_store=context_store
        self.setWindowTitle("Workspace bindings"); self.resize(470,420)
        root=QVBoxLayout(self); root.setContentsMargins(20,18,20,18); root.setSpacing(11)
        root.addWidget(_title("Workspace bindings",20)); root.addWidget(_muted(f"{account_label}\nChoose where this connected account may be used. OAuth credentials stay local; only this local binding is changed."))
        context=context_store.load(); explicit=set(context.connector_bindings.get(provider,{}).get(account_id,())); has_explicit=account_id in context.connector_bindings.get(provider,{})
        self.checks={}
        for key,descriptor in context.workspaces.items():
            check=QCheckBox(f"{descriptor.name}  ·  {descriptor.plan.label}"+(f"  ·  {descriptor.role.title()}" if descriptor.role else "")); check.setChecked(key in explicit if has_explicit else True); self.checks[key]=check; root.addWidget(check)
        note=_muted("The same personal Gmail/Drive account may be enabled in several client workspaces. The active workspace determines which PrivacyGate policy is applied."); note.setStyleSheet(f"background:{SOFT};border:1px solid {BORDER};border-radius:9px;padding:10px;color:{MUTED};font-size:9px;"); root.addWidget(note); root.addStretch(1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Save); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def save(self): self.context_store.bind_account(self.provider,self.account_id,[key for key,check in self.checks.items() if check.isChecked()])


def _build_apps_page(page):
    shell=QWidget(); layout=QVBoxLayout(shell); layout.setContentsMargins(0,0,0,0); layout.setSpacing(10)
    intro=_card(); row=QHBoxLayout(intro); row.setContentsMargins(16,12,16,12); row.addWidget(_title("Apps & AI")); row.addWidget(_muted("Connect once. Use across workspaces. Connector credentials remain encrypted/local; the selected workspace decides which policy applies."),1); layout.addWidget(intro)
    columns=QHBoxLayout(); columns.setSpacing(10)
    accounts=_card(); box=QVBoxLayout(accounts); box.setContentsMargins(15,13,15,13); box.addWidget(_title("Connected accounts")); box.addWidget(_muted("Real accounts already connected in PrivacyGate."))
    page.workspace_accounts_table=QTableWidget(0,4); page.workspace_accounts_table.setHorizontalHeaderLabels(["Connector","Account","Usable in workspaces",""]); page.workspace_accounts_table.verticalHeader().setVisible(False); page.workspace_accounts_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); page.workspace_accounts_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); page.workspace_accounts_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch); page.workspace_accounts_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents); box.addWidget(page.workspace_accounts_table,1)
    page.manage_binding_button=QPushButton("Manage workspace bindings",objectName="Primary"); box.addWidget(page.manage_binding_button); columns.addWidget(accounts,3)
    approval=_card(); abox=QVBoxLayout(approval); abox.setContentsMargins(15,13,15,13); abox.addWidget(_title("Policy for active workspace")); page.workspace_policy_summary=_muted(); abox.addWidget(page.workspace_policy_summary)
    page.ai_grid=QGridLayout(); abox.addLayout(page.ai_grid); page.ai_tiles={}
    for index,(provider,label) in enumerate(AI_PROVIDERS):
        tile=QFrame(); tile.setStyleSheet(f"QFrame{{background:{SOFT};border:1px solid {BORDER};border-radius:10px;}}"); t=QVBoxLayout(tile); t.setContentsMargins(10,9,10,9); icon=QLabel(); icon.setFixedSize(34,34); icon.setAlignment(Qt.AlignmentFlag.AlignCenter); name=QLabel(label); name.setStyleSheet(f"color:{NAVY};font-weight:900;"); status=QLabel("—"); t.addWidget(icon,alignment=Qt.AlignmentFlag.AlignCenter); t.addWidget(name,alignment=Qt.AlignmentFlag.AlignCenter); t.addWidget(status,alignment=Qt.AlignmentFlag.AlignCenter); page.ai_tiles[provider]=(icon,status); page.ai_grid.addWidget(tile,0,index)
    abox.addWidget(_title("Approved Apps",12)); page.apps_grid=QGridLayout(); abox.addLayout(page.apps_grid); page.app_tiles={}
    for index,(provider,label) in enumerate(PROVIDERS):
        tile=QFrame(); tile.setStyleSheet("QFrame{background:#FFFFFF;border:none;}"); r=QHBoxLayout(tile); r.setContentsMargins(2,3,2,3); icon=QLabel(); icon.setFixedSize(24,24); name=QLabel(label); name.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:800;"); status=QLabel("—"); r.addWidget(icon); r.addWidget(name,1); r.addWidget(status); page.app_tiles[provider]=(icon,status); page.apps_grid.addWidget(tile,index//2,index%2)
    abox.addStretch(1); columns.addWidget(approval,2); layout.addLayout(columns,1)
    note=_muted("Connectors and data remain on this device. PrivacyGate never copies OAuth tokens into the Organization control plane."); note.setStyleSheet(f"background:#EDF8F4;border:1px solid #B9DECD;border-radius:9px;padding:10px;color:{GREEN};font-size:9px;"); layout.addWidget(note); return shell


def _account_rows(page):
    apps_page=getattr(page.window(),"apps_hub_page",None); service=getattr(apps_page,"service",None); result=[]
    if service is None: return result
    for provider,label in PROVIDERS:
        try: records=tuple(service.list_connected_accounts(provider))
        except Exception: records=()
        for record in records: result.append((provider,label,str(getattr(record,"account_id","") or ""),str(getattr(record,"label","") or label)))
    return result


def _render_apps(page):
    table=getattr(page,"workspace_accounts_table",None)
    if table is None: return
    rows=_account_rows(page); context=page._privacygate_workspace_store.load(); table.setRowCount(len(rows))
    for row_index,(provider,provider_label,account_id,account_label) in enumerate(rows):
        p=QTableWidgetItem(provider_label); p.setData(Qt.ItemDataRole.UserRole,provider); p.setData(int(Qt.ItemDataRole.UserRole)+1,account_id); table.setItem(row_index,0,p); table.setItem(row_index,1,QTableWidgetItem(account_label))
        bindings=context.connector_bindings.get(provider,{}).get(account_id); names=[item.name for item in context.workspaces.values()] if bindings is None else [context.workspaces[key].name for key in bindings if key in context.workspaces]; table.setItem(row_index,2,QTableWidgetItem(", ".join(names) if names else "Not assigned"))
        available=page._privacygate_workspace_store.is_account_available(provider,account_id,context.active_key); table.setItem(row_index,3,QTableWidgetItem("Available" if available else "Not in workspace"))
    descriptor=context.workspaces.get(context.active_key); policy=page.state.policy
    if descriptor and descriptor.personal: page.workspace_policy_summary.setText(f"{descriptor.name} • {descriptor.plan.label}\nPersonal workspace: no company policy is applied.")
    elif policy: page.workspace_policy_summary.setText(f"{policy.organization_name} • {policy.plan.label} • Policy v{policy.version}\nMandatory protection and approved destinations are enforced locally.")
    else: page.workspace_policy_summary.setText("Workspace policy unavailable.")
    for provider,(_icon,status) in page.ai_tiles.items():
        allowed=True if descriptor and descriptor.personal else bool(policy and policy.allowed_ai.get("other" if provider=="gemini" else provider,False)); status.setText("Allowed" if allowed else "Blocked"); status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:9px;font-weight:900;")
    for provider,(_icon,status) in page.app_tiles.items():
        allowed=True if descriptor and descriptor.personal else bool(policy and policy.allowed_connectors.get(provider,policy.allowed_connectors.get("*",False))); status.setText("✓" if allowed else "Blocked"); status.setStyleSheet(f"color:{GREEN if allowed else RED};font-size:8px;font-weight:900;")


def _load_tile_logos(page):
    for provider,(label,_status) in page.app_tiles.items(): page._privacygate_logo_loader.load(provider,lambda pixmap,target=label: target.setPixmap(pixmap.scaled(22,22,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)))
    for provider,(label,_status) in page.ai_tiles.items(): page._privacygate_logo_loader.load(provider,lambda pixmap,target=label: target.setPixmap(pixmap.scaled(32,32,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)))


def install_multi_workspace_experience():
    global _INSTALLED
    if _INSTALLED: return
    _INSTALLED=True
    previous_build=TeamPage._build_ui; previous_render=TeamPage._render; previous_apply=TeamPage._apply_state
    def build(self):
        self._privacygate_workspace_store=WorkspaceContextStore(self.state_store.data_dir,self.identity_store.secrets); self._privacygate_logo_loader=ProviderLogoLoader(self.state_store.data_dir,self); previous_build(self)
        selector=_card(); r=QHBoxLayout(selector); r.setContentsMargins(14,10,14,10); r.addWidget(_title("Active workspace",12)); self.workspace_selector=QComboBox(); self.workspace_selector.setMinimumWidth(330); r.addWidget(self.workspace_selector); self.workspace_context_note=_muted(); r.addWidget(self.workspace_context_note,1); root=self.layout(); root.insertWidget(1,selector)
        apps_page=_build_apps_page(self); apps_index=self.sections.addWidget(apps_page); self._privacygate_apps_index=apps_index; button=QPushButton("Apps & AI"); button.setCheckable(True); button.setAutoExclusive(True); button.clicked.connect(lambda _checked=False:self._show_section(apps_index)); nav=_find_layout_containing(self.organization_shell.layout(),self.section_buttons[0]); position=nav.indexOf(self.section_buttons[3]) if nav is not None else -1
        if nav is not None: nav.insertWidget(max(0,position),button)
        self.section_buttons.append(button); self.workspace_selector.currentIndexChanged.connect(self._privacygate_workspace_selected); self.manage_binding_button.clicked.connect(self._privacygate_manage_binding); _load_tile_logos(self)
    def render_selector(self):
        context=self._privacygate_workspace_store.load(); self.workspace_selector.blockSignals(True); self.workspace_selector.clear()
        for key,d in context.workspaces.items(): self.workspace_selector.addItem(f"{d.name}  ·  {d.plan.label}  ·  {d.role.title() if d.role else 'You'}",key)
        self.workspace_selector.setCurrentIndex(max(0,self.workspace_selector.findData(context.active_key))); self.workspace_selector.blockSignals(False); d=context.workspaces.get(context.active_key); self.workspace_context_note.setText("Personal workspace • your existing Protect experience stays unchanged." if d and d.personal else (f"Managed by {d.name} • company policy is active in this workspace." if d else ""))
    def render(self): previous_render(self); render_selector(self); _render_apps(self); context=self._privacygate_workspace_store.load(); d=context.workspaces.get(context.active_key); self.section_buttons[-1].setVisible(bool(d and not d.personal))
    def refresh(self,*,show_errors):
        if self._active_worker is not None: return
        from ai_pm_lab_privacy_gate.ui.workers import FunctionWorker
        def task():
            session=self.account_client.restore_session()
            if session is None: return None
            individual=self.team_client._individual_state(session); descriptors=tuple(self.team_client.list_workspace_descriptors(session)); context=self._privacygate_workspace_store.cache_workspaces(descriptors,personal_plan=individual.plan)
            if context.active_key=="personal" and self.state.organization_id and f"org:{self.state.organization_id}" in context.workspaces: context=self._privacygate_workspace_store.set_active(f"org:{self.state.organization_id}")
            d=context.workspaces.get(context.active_key)
            if d is None or d.personal: return individual,[],[],context.active_key
            state=self.team_client.fetch_workspace_state(session,d.organization_id); self._privacygate_workspace_store.cache_state(context.active_key,state); members=[]; devices=[]
            if state.role in {"owner","admin","manager"}: members=self.team_client.list_members(session,state.organization_id); devices=self.team_client.list_devices(session,state.organization_id)
            return state,members,devices,context.active_key
        worker=FunctionWorker(task); self._active_worker=worker; self._set_busy(True)
        def ready(payload):
            if payload is None: self._render(); return
            state,members,devices,key=payload; self._privacygate_workspace_store.cache_state(key,state); self._apply_state(state,members,devices)
        worker.signals.result.connect(ready)
        if show_errors: worker.signals.error.connect(lambda message: QMessageBox.warning(self,"Workspace sync unavailable",message))
        worker.signals.finished.connect(self._worker_finished); self.thread_pool.start(worker)
    def apply_state(self,state,members=None,devices=None): previous_apply(self,state,members,devices); context=self._privacygate_workspace_store.load(); key="personal" if not state.organization_id else f"org:{state.organization_id}"; self._privacygate_workspace_store.cache_state(key,state) if key in context.workspaces else None
    def selected(self,_index):
        key=str(self.workspace_selector.currentData() or "")
        if not key: return
        try: self._privacygate_workspace_store.set_active(key)
        except KeyError: return
        cached=self._privacygate_workspace_store.cached_state(key)
        if cached is not None: self.state_store.save(cached); self.state=cached; self.policy_changed.emit(cached.policy); self.state_changed.emit(cached); self._render()
        self.refresh_silent()
    def binding(self):
        row=self.workspace_accounts_table.currentRow()
        if row<0: QMessageBox.information(self,"Select an account","Select a connected account first."); return
        p=self.workspace_accounts_table.item(row,0); a=self.workspace_accounts_table.item(row,1)
        if p is None or a is None: return
        provider=str(p.data(Qt.ItemDataRole.UserRole) or ""); account_id=str(p.data(int(Qt.ItemDataRole.UserRole)+1) or "")
        if not provider or not account_id: return
        dialog=WorkspaceBindingsDialog(provider=provider,account_id=account_id,account_label=a.text(),context_store=self._privacygate_workspace_store,parent=self)
        if dialog.exec()==QDialog.DialogCode.Accepted: dialog.save(); _render_apps(self)
    TeamPage._build_ui=build; TeamPage._render=render; TeamPage._refresh=refresh; TeamPage._apply_state=apply_state; TeamPage._privacygate_workspace_selected=selected; TeamPage._privacygate_manage_binding=binding
