from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ai_pm_lab_privacy_gate.domain.company_policy import ProtectionDirective
from ai_pm_lab_privacy_gate.ui.business_foundation import _engine_for_page
from ai_pm_lab_privacy_gate.ui.protection_page import ProtectionPage

_INSTALLED=False
NAVY="#062B4F"; GREEN="#23824B"; MUTED="#61798A"; BORDER="#DCE5EA"

def _combined_original(page):
    document=getattr(page,"current_document",None)
    if document is None: return ""
    pages=tuple(getattr(document,"pages",()) or ())
    if len(pages)==1: return str(getattr(pages[0],"text","") or "")
    return "\n\n".join(f"--- Page {getattr(item,'page_number',index+1)} ---\n{getattr(item,'text','')}" for index,item in enumerate(pages))

def _managed_active(page):
    engine=_engine_for_page(page); return bool(engine.active and engine.policy is not None)

def _update_header(page):
    active=_managed_active(page); page._managed_context_card.setVisible(active); page._managed_preview_switch.setVisible(active)
    if not active:
        page.original_document_panel.setVisible(True); page.protected_document_panel.setVisible(True); return
    engine=_engine_for_page(page); policy=engine.policy
    if policy is None: return
    role=""; state=getattr(getattr(page.window(),"team_page",None),"state",None)
    if state is not None: role=str(getattr(state,"role","") or "").title()
    page._managed_context_title.setText(f"🏢  {policy.organization_name}    •    {policy.plan.label}"+(f"    •    {role}" if role else "")); page._managed_context_detail.setText(f"Managed workspace • {policy.policy_name} v{policy.version}. Company-required protection is enforced before save and AI handoff.")
    required={entity for entity,directive in policy.protection_rules.items() if directive is ProtectionDirective.REQUIRED_PROTECT}; total=sum(1 for f in getattr(page,"current_findings",()) if str(getattr(f,"entity_type","") or "").upper() in required); selected=tuple(page._selected_findings()) if getattr(page,"current_findings",()) else (); protected=sum(1 for f in selected if str(getattr(f,"entity_type","") or "").upper() in required); allowed=[key.title() for key,enabled in policy.allowed_ai.items() if enabled]
    page._managed_policy_summary.setText(f"🛡  Mandatory protected: {protected}/{total}    •    Approved AI: {', '.join(allowed) or 'None'}    •    Second scan runs before AI handoff")

def _decorate(page):
    if not _managed_active(page): return
    engine=_engine_for_page(page)
    for row in range(page.findings_table.rowCount()):
        item=page.findings_table.item(row,1); checkbox=page.findings_table.item(row,0)
        if item is None or checkbox is None: continue
        finding_id=str(checkbox.data(Qt.ItemDataRole.UserRole) or ""); finding=next((v for v in page.current_findings if str(getattr(v,"finding_id","") or "")==finding_id),None)
        if finding is None: continue
        entity=str(getattr(finding,"entity_type","") or "").upper(); directive=engine.directive_for(entity); suffix={ProtectionDirective.REQUIRED_PROTECT:"  •  Required 🔒",ProtectionDirective.DEFAULT_PROTECT:"  •  Default protect 🛡",ProtectionDirective.USER_CHOICE:"  •  User choice",ProtectionDirective.ALLOW:"  •  Allowed"}[directive]; item.setText(entity.replace("_"," ").title()+suffix); item.setToolTip("Company required — cannot be unprotected." if directive is ProtectionDirective.REQUIRED_PROTECT else f"Company policy: {suffix.replace('•','').strip()}")

def _apply_view(page):
    if not _managed_active(page): return
    mode=getattr(page,"_managed_preview_mode","anonymized"); page._managed_original_button.setChecked(mode=="original"); page._managed_anonymized_button.setChecked(mode=="anonymized"); page._managed_compare_button.setChecked(mode=="compare")
    if page.preview_tabs.isTabVisible(1):
        page.preview_tabs.setCurrentIndex(1); page.original_document_panel.setVisible(mode in {"original","compare"}); page.protected_document_panel.setVisible(mode in {"anonymized","compare"}); page.document_preview_splitter.setSizes([1200,0] if mode=="original" else ([0,1200] if mode=="anonymized" else [600,600]))
    else:
        page.preview_tabs.setCurrentIndex(0)
        if mode=="original": page.preview.setPlainText(_combined_original(page))
        elif getattr(page,"current_result",None) is not None: page.preview.setPlainText(page.current_result.combined_text)

def install_managed_protect_experience():
    global _INSTALLED
    if _INSTALLED: return
    _INSTALLED=True
    previous_build=ProtectionPage._build_ui; previous_populate=ProtectionPage._populate_findings; previous_refresh=ProtectionPage._refresh_preview; previous_compare=ProtectionPage._update_document_comparison; previous_policy=ProtectionPage._privacygate_set_policy_engine
    def build(self):
        previous_build(self); context=QFrame(); context.setObjectName("ManagedWorkspaceContext"); context.setStyleSheet("QFrame#ManagedWorkspaceContext{background:#F0F9FA;border:1px solid #B8E1E4;border-radius:11px;}"); layout=QVBoxLayout(context); layout.setContentsMargins(14,10,14,10); layout.setSpacing(3); self._managed_context_title=QLabel(); self._managed_context_title.setStyleSheet(f"color:{NAVY};font-size:12px;font-weight:950;"); self._managed_context_detail=QLabel(); self._managed_context_detail.setWordWrap(True); self._managed_context_detail.setStyleSheet(f"color:{MUTED};font-size:9px;"); self._managed_policy_summary=QLabel(); self._managed_policy_summary.setWordWrap(True); self._managed_policy_summary.setStyleSheet(f"color:{GREEN};font-size:9px;font-weight:900;"); layout.addWidget(self._managed_context_title); layout.addWidget(self._managed_context_detail); layout.addWidget(self._managed_policy_summary); self._managed_context_card=context; self.layout().insertWidget(1,context)
        switch=QFrame(); switch.setObjectName("ManagedPreviewSwitch"); switch.setStyleSheet(f"QFrame#ManagedPreviewSwitch{{background:#FFFFFF;border:1px solid {BORDER};border-radius:9px;}}"); row=QHBoxLayout(switch); row.setContentsMargins(7,6,7,6); row.setSpacing(5); label=QLabel("Document view"); label.setStyleSheet(f"color:{NAVY};font-size:9px;font-weight:900;"); row.addWidget(label); self._managed_original_button=QPushButton("Original"); self._managed_anonymized_button=QPushButton("Anonymized file"); self._managed_compare_button=QPushButton("Compare"); group=QButtonGroup(self); group.setExclusive(True)
        for button in (self._managed_original_button,self._managed_anonymized_button,self._managed_compare_button): button.setCheckable(True); button.setStyleSheet("QPushButton{background:#F7FAFC;color:#17384E;border:1px solid #DCE5EA;border-radius:7px;padding:6px 10px;font-size:9px;font-weight:850;}QPushButton:checked{background:#0B7180;color:#FFFFFF;border-color:#0B7180;}"); group.addButton(button); row.addWidget(button)
        row.addStretch(1); self._managed_preview_switch=switch; self._managed_preview_mode="anonymized"; self.preview_card.layout().insertWidget(1,switch)
        def set_mode(mode): self._managed_preview_mode=mode; previous_refresh(self) if mode!="original" else None; _apply_view(self)
        self._managed_original_button.clicked.connect(lambda _checked=False:set_mode("original")); self._managed_anonymized_button.clicked.connect(lambda _checked=False:set_mode("anonymized")); self._managed_compare_button.clicked.connect(lambda _checked=False:set_mode("compare")); self._managed_anonymized_button.setChecked(True); _update_header(self)
    def populate(self): previous_populate(self); _decorate(self); _update_header(self)
    def refresh(self): previous_refresh(self); _apply_view(self); _update_header(self)
    def compare(self): previous_compare(self); _apply_view(self)
    def policy(self,engine): previous_policy(self,engine); _update_header(self); _decorate(self); _apply_view(self)
    ProtectionPage._build_ui=build; ProtectionPage._populate_findings=populate; ProtectionPage._refresh_preview=refresh; ProtectionPage._update_document_comparison=compare; ProtectionPage._privacygate_set_policy_engine=policy
