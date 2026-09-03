from pathlib import Path

path = Path("src/ai_pm_lab_privacy_gate/infrastructure/pii/presidio_engine.py")
text = path.read_text(encoding="utf-8")
old = '    "MAINTENANCE_TICKET_ID": {"management"},\n    "VEHICLE_LICENSE_PLATE": {"is ready for"},\n'
new = '    "MAINTENANCE_TICKET_ID": {"management"},\n    "PASSWORD_CREDENTIAL": {"requirement", "requirements"},\n    "VEHICLE_LICENSE_PLATE": {"is ready for"},\n'
if old not in text:
    if '"PASSWORD_CREDENTIAL": {"requirement", "requirements"}' in text:
        print("Final password guardrail already applied.")
        raise SystemExit(0)
    raise SystemExit("Expected presidio_engine.py anchor not found; no changes made.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Applied final PASSWORD_CREDENTIAL false-value guardrail.")
