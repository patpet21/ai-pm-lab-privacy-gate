from __future__ import annotations
import csv, json, subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from ai_pm_lab_privacy_gate.application.privacy_service import PrivacyGateService
from ai_pm_lab_privacy_gate.domain.models import AnalysisDocument, PageContent
from ai_pm_lab_privacy_gate.domain.profiles import entities_for_scope, get_profile

EXPECTED_CASES=100
EXPECTED_SPANS=83
EXPECTED_NEGATIVES=30
OUT_CSV=Path("build/benchmarks/english_blind_v1.csv")
OUT_JSON=Path("build/benchmarks/english_blind_v1_summary.json")
RELAXED_OVERLAP=.80

RAW_CASES=[('BLIND-ID-001', 'identity', 'Please send the revised lease to Mateo Alvarez before 4 PM.', [('PERSON', 'Mateo Alvarez')]), ('BLIND-ID-002', 'identity', 'Prepared for: Chloe Bennett', [('PERSON', 'Chloe Bennett')]), ('BLIND-ID-003', 'identity', 'Primary contact — Noor Rahman', [('PERSON', 'Noor Rahman')]), ('BLIND-ID-004', 'identity', 'The closing attorney is Sophia M. Greene.', [('PERSON', 'Sophia M. Greene')]), ('BLIND-ID-005', 'identity', 'Vendor: Harbor Crest Engineering LLC', [('ORGANIZATION', 'Harbor Crest Engineering LLC')]), ('BLIND-ID-006', 'identity', 'The report was issued by Meridian Property Advisors Inc.', [('ORGANIZATION', 'Meridian Property Advisors Inc.')]), ('BLIND-ID-007', 'identity', 'Employer = Northpoint Data Systems Corp.', [('ORGANIZATION', 'Northpoint Data Systems Corp.')]), ('BLIND-ID-008', 'identity', 'The inspection will take place in Hoboken.', [('LOCATION', 'Hoboken')]), ('BLIND-ID-009', 'identity', 'Service area: Westchester County', [('LOCATION', 'Westchester County')]), ('BLIND-ID-010', 'identity', 'Forwarding address: 318 East 92nd Street, Apt. 7C', [('STREET_ADDRESS', '318 East 92nd Street, Apt. 7C')]), ('BLIND-ID-011', 'identity', 'Office location = 770 Lexington Avenue, Suite 2100', [('STREET_ADDRESS', '770 Lexington Avenue, Suite 2100')]), ('BLIND-ID-012', 'identity', 'Email: nina.patel+ops@example.com', [('EMAIL_ADDRESS', 'nina.patel+ops@example.com')]), ('BLIND-ID-013', 'identity', 'Telephone: (347) 555-0164', [('PHONE_NUMBER', '(347) 555-0164')]), ('BLIND-ID-014', 'identity', 'Call 646-555-0182 extension 305', [('PHONE_NUMBER', '646-555-0182 extension 305')]), ('BLIND-ID-015', 'identity', 'ZIP code: 11231-4402', [('POSTAL_CODE', '11231-4402')]), ('BLIND-GOV-001', 'government', 'SSN = 317-42-8801', [('US_SSN', '317-42-8801')]), ('BLIND-GOV-002', 'government', 'Social Security no. 604-18-2397', [('US_SSN', '604-18-2397')]), ('BLIND-GOV-003', 'government', 'ITIN: 923-61-7742', [('US_ITIN', '923-61-7742')]), ('BLIND-GOV-004', 'government', 'Passport No. Z76543210', [('US_PASSPORT', 'Z76543210')]), ('BLIND-GOV-005', 'government', 'U.S. Passport No. 456789123', [('US_PASSPORT', '456789123')]), ('BLIND-GOV-006', 'government', 'DL No. B-731-550-92', [('US_DRIVER_LICENSE', 'B-731-550-92')]), ('BLIND-GOV-007', 'government', "Driver's license: R8842017", [('US_DRIVER_LICENSE', 'R8842017')]), ('BLIND-GOV-008', 'government', 'Date of birth: 1991-11-06', [('DATE_OF_BIRTH', '1991-11-06')]), ('BLIND-GOV-009', 'government', 'Birth date = September 3, 1979', [('DATE_OF_BIRTH', 'September 3, 1979')]), ('BLIND-GOV-010', 'government', 'Client IP address: 198.51.100.27', [('IP_ADDRESS', '198.51.100.27')]), ('BLIND-FIN-001', 'financial', 'Checking account number: 004455667788', [('US_BANK_NUMBER', '004455667788')]), ('BLIND-FIN-002', 'financial', 'Routing number = 021200025', [('US_ROUTING_NUMBER', '021200025')]), ('BLIND-FIN-003', 'financial', 'ABA # 026073150', [('US_ROUTING_NUMBER', '026073150')]), ('BLIND-FIN-004', 'financial', 'SWIFT/BIC = BOFAUS6S', [('SWIFT_BIC', 'BOFAUS6S')]), ('BLIND-FIN-005', 'financial', 'Card: 4000 0566 5566 5556', [('CREDIT_CARD', '4000 0566 5566 5556')]), ('BLIND-FIN-006', 'financial', 'Visa ending in 4821', [('CARD_LAST_FOUR', '4821')]), ('BLIND-FIN-007', 'financial', 'Wire amount: USD 48,750.00', [('MONEY_AMOUNT', 'USD 48,750.00')]), ('BLIND-FIN-008', 'financial', 'Refund processed for -$742.18', [('MONEY_AMOUNT', '-$742.18')]), ('BLIND-FIN-009', 'financial', 'Merchant: Riverside Organic Market', [('MERCHANT', 'Riverside Organic Market')]), ('BLIND-FIN-010', 'financial', 'Issued by Bluebird Coffee Roasters', [('MERCHANT', 'Bluebird Coffee Roasters')]), ('BLIND-FIN-011', 'financial', 'Sent money to Julian Foster with reference security deposit', [('COUNTERPARTY', 'Julian Foster'), ('TRANSACTION_REFERENCE', 'security deposit')]), ('BLIND-FIN-012', 'financial', 'Transaction ID: TXN-2026-90441', [('TRANSACTION_ID', 'TXN-2026-90441')]), ('BLIND-FIN-013', 'financial', 'Statement reference: 7c1e4a11-cc35-43d2-8fe2-17f71c423222', [('STATEMENT_REFERENCE', '7c1e4a11-cc35-43d2-8fe2-17f71c423222')]), ('BLIND-FIN-014', 'financial', 'IBAN = GB33BUKB20201555555555', [('IBAN_CODE', 'GB33BUKB20201555555555')]), ('BLIND-FIN-015', 'financial', 'Beneficiary IBAN: NL91ABNA0417164300', [('IBAN_CODE', 'NL91ABNA0417164300')]), ('BLIND-BIZ-001', 'business_real_estate', 'Invoice No. INV-2026-7719', [('INVOICE_NUMBER', 'INV-2026-7719')]), ('BLIND-BIZ-002', 'business_real_estate', 'Purchase order ID = PO-88420-A', [('PURCHASE_ORDER_ID', 'PO-88420-A')]), ('BLIND-BIZ-003', 'business_real_estate', 'Contract reference: CT-2026-1188', [('CONTRACT_ID', 'CT-2026-1188')]), ('BLIND-BIZ-004', 'business_real_estate', 'Customer ID: CUST-441992', [('CUSTOMER_ID', 'CUST-441992')]), ('BLIND-BIZ-005', 'business_real_estate', 'Employee identifier = EMP-73015', [('EMPLOYEE_ID', 'EMP-73015')]), ('BLIND-BIZ-006', 'business_real_estate', 'Tenant ID: TEN-88412', [('TENANT_ID', 'TEN-88412')]), ('BLIND-BIZ-007', 'business_real_estate', 'Lease number = L-2026-9920', [('LEASE_ID', 'L-2026-9920')]), ('BLIND-BIZ-008', 'business_real_estate', 'NYC BBL: 3012340044', [('NYC_BBL', '3012340044')]), ('BLIND-BIZ-009', 'business_real_estate', 'Legal rent: $4,925.00', [('RENT_AMOUNT', '$4,925.00')]), ('BLIND-BIZ-010', 'business_real_estate', 'Security deposit balance = $9,850.00', [('SECURITY_DEPOSIT_AMOUNT', '$9,850.00')]), ('BLIND-BIZ-011', 'business_real_estate', 'Purchase price — $1,245,000', [('PURCHASE_PRICE', '$1,245,000')]), ('BLIND-BIZ-012', 'business_real_estate', 'Broker commission: 4.5%', [('BROKER_COMMISSION', '4.5%')]), ('BLIND-BIZ-013', 'business_real_estate', 'Contractor license No. NYC-HIC-2188441', [('CONTRACTOR_LICENSE', 'NYC-HIC-2188441')]), ('BLIND-BIZ-014', 'business_real_estate', 'Safe combination: 18-44-92', [('SAFE_COMBINATION', '18-44-92')]), ('BLIND-BIZ-015', 'business_real_estate', 'Building Wi-Fi password: Riverview!2026', [('WIFI_CREDENTIAL', 'Riverview!2026')]), ('BLIND-SEC-001', 'secrets', 'OpenAI API key: sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456', [('API_KEY', 'sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz123456')]), ('BLIND-SEC-002', 'secrets', 'GitHub access token = ghp_AbCdEf1234567890GhIjKlMnOpQrStUvWxYz', [('ACCESS_TOKEN', 'ghp_AbCdEf1234567890GhIjKlMnOpQrStUvWxYz')]), ('BLIND-SEC-003', 'secrets', 'Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJ1c2VyIjoiYWJjMTIzIn0.SIGNATURE987654', [('JWT_TOKEN', 'eyJhbGciOiJSUzI1NiJ9.eyJ1c2VyIjoiYWJjMTIzIn0.SIGNATURE987654')]), ('BLIND-SEC-004', 'secrets', 'OAuth client secret: oauth_ClientSecret_77AaBbCcDdEe', [('OAUTH_SECRET', 'oauth_ClientSecret_77AaBbCcDdEe')]), ('BLIND-SEC-005', 'secrets', 'AWS access key ID = AKIAABCDEFGHIJKLMNOP', [('CLOUD_CREDENTIAL', 'AKIAABCDEFGHIJKLMNOP')]), ('BLIND-SEC-006', 'secrets', 'Database URL = postgres://svc_user:UltraPass-77@db.internal.invalid:5432/core', [('DATABASE_CREDENTIAL', 'postgres://svc_user:UltraPass-77@db.internal.invalid:5432/core')]), ('BLIND-SEC-007', 'secrets', 'Webhook signing secret = whsec_AbCdEfGhIjKlMnOpQrStUvWx', [('WEBHOOK_SECRET', 'whsec_AbCdEfGhIjKlMnOpQrStUvWx')]), ('BLIND-SEC-008', 'secrets', 'Device MAC: AA:BB:CC:11:22:33', [('MAC_ADDRESS', 'AA:BB:CC:11:22:33')]), ('BLIND-SEC-009', 'secrets', 'Bitcoin address = 1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY', [('CRYPTO', '1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY')]), ('BLIND-SEC-010', 'secrets', 'Private key:\n-----BEGIN PRIVATE KEY-----\nQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=\n-----END PRIVATE KEY-----', [('PRIVATE_KEY', '-----BEGIN PRIVATE KEY-----\nQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=\n-----END PRIVATE KEY-----')]), ('BLIND-MIX-001', 'mixed', 'Please contact Elena Rossi at elena.rossi@example.net. Her DOB is 12/09/1985 and her phone is 917-555-0128.', [('PERSON', 'Elena Rossi'), ('EMAIL_ADDRESS', 'elena.rossi@example.net'), ('DATE_OF_BIRTH', '12/09/1985'), ('PHONE_NUMBER', '917-555-0128')]), ('BLIND-MIX-002', 'mixed', 'Vendor = Atlas Restoration Group LLC\nInvoice No. INV-8841-Q\nInvoice total: $18,420.00', [('ORGANIZATION', 'Atlas Restoration Group LLC'), ('INVOICE_NUMBER', 'INV-8841-Q'), ('INVOICE_AMOUNT', '$18,420.00')]), ('BLIND-MIX-003', 'mixed', 'Tenant ID: TEN-44109\nLease number: L-2026-44109\nProperty: 95 River Road Unit 8B\nLegal rent = $3,875', [('TENANT_ID', 'TEN-44109'), ('LEASE_ID', 'L-2026-44109'), ('STREET_ADDRESS', '95 River Road Unit 8B'), ('RENT_AMOUNT', '$3,875')]), ('BLIND-MIX-004', 'mixed', 'Beneficiary IBAN = DE12500105170648489890\nSWIFT/BIC: INGDDEFF\nWire amount = EUR 72,500.00', [('IBAN_CODE', 'DE12500105170648489890'), ('SWIFT_BIC', 'INGDDEFF'), ('MONEY_AMOUNT', 'EUR 72,500.00')]), ('BLIND-MIX-005', 'mixed', 'API key = sk-AbCdEfGhIjKlMnOpQrStUvWxYz0987654321\nWebhook secret: whsec_XyZ987654321AbCdEfGh\nDevice MAC address = 10:20:30:40:50:60', [('API_KEY', 'sk-AbCdEfGhIjKlMnOpQrStUvWxYz0987654321'), ('WEBHOOK_SECRET', 'whsec_XyZ987654321AbCdEfGh'), ('MAC_ADDRESS', '10:20:30:40:50:60')]), ('BLIND-NEG-001', 'negative', 'API key rotation is scheduled for next Friday.', []), ('BLIND-NEG-002', 'negative', 'The GitHub token policy requires quarterly review.', []), ('BLIND-NEG-003', 'negative', 'Authorization: Bearer <access-token>', []), ('BLIND-NEG-004', 'negative', 'OAuth client secret fields are hidden by default.', []), ('BLIND-NEG-005', 'negative', 'AWS access key ID values should never be pasted into chat.', []), ('BLIND-NEG-006', 'negative', 'Database URL configuration is described in the runbook.', []), ('BLIND-NEG-007', 'negative', 'Webhook signing secret rotation is automatic.', []), ('BLIND-NEG-008', 'negative', 'Device MAC address formatting uses six hexadecimal pairs.', []), ('BLIND-NEG-009', 'negative', 'Bitcoin address validation failed because the field was empty.', []), ('BLIND-NEG-010', 'negative', '-----BEGIN PRIVATE KEY----- appears in the documentation header example.', []), ('BLIND-NEG-011', 'negative', 'The passport renewal process changed this year.', []), ('BLIND-NEG-012', 'negative', 'Driver license policy is covered in the employee handbook.', []), ('BLIND-NEG-013', 'negative', 'Date of birth is a required field in the paper form.', []), ('BLIND-NEG-014', 'negative', 'The organization will meet in the conference room.', []), ('BLIND-NEG-015', 'negative', 'Main Street traffic will be rerouted tomorrow.', []), ('BLIND-NEG-016', 'negative', 'Invoice processing begins after manager approval.', []), ('BLIND-NEG-017', 'negative', 'The rent policy was revised after the annual review.', []), ('BLIND-NEG-018', 'negative', 'Security deposit rules differ by jurisdiction.', []), ('BLIND-NEG-019', 'negative', 'Broker commission policy follows the signed agreement.', []), ('BLIND-NEG-020', 'negative', 'Routing changes were deployed to the payment service.', []), ('BLIND-NEG-021', 'negative', 'Checking the account summary does not require credentials.', []), ('BLIND-NEG-022', 'negative', 'Merchant services will conduct training next week.', []), ('BLIND-NEG-023', 'negative', 'Customer ID fields are optional in the template.', []), ('BLIND-NEG-024', 'negative', 'Tenant ID mapping is handled by the migration script.', []), ('BLIND-NEG-025', 'negative', 'The safe combination procedure is documented separately.', []), ('BLIND-NEG-026', 'negative', 'Wi-Fi password requirements now require 16 characters.', []), ('BLIND-NEG-027', 'negative', 'Room 503 is reserved for onboarding.', []), ('BLIND-NEG-028', 'negative', 'Version 20261106 identifies the release build.', []), ('BLIND-NEG-029', 'negative', 'The estimate increased by $1,200 because of material costs.', []), ('BLIND-NEG-030', 'negative', 'Please send the file to the person responsible for procurement.', [])]

def build_cases():
    cases=[]
    for cid,group,text,pairs in RAW_CASES:
        expected=[]
        cursor=0
        for entity,value in pairs:
            start=text.find(value,cursor)
            if start<0:
                start=text.find(value)
            if start<0:
                raise ValueError(f"{cid} missing expected {entity}={value!r}")
            expected.append({"entity_type":entity,"value":value,"page_number":1,"start":start,"end":start+len(value)})
            cursor=start+len(value)
        cases.append({"id":cid,"group":group,"text":text,"expected":expected})
    spans=sum(len(c["expected"]) for c in cases)
    neg=sum(not c["expected"] for c in cases)
    if (len(cases),spans,neg)!=(EXPECTED_CASES,EXPECTED_SPANS,EXPECTED_NEGATIVES):
        raise ValueError(f"Frozen blind corpus changed: {len(cases)},{spans},{neg}")
    return cases

def metric(tp,fp,fn):
    p=tp/(tp+fp) if tp+fp else 1.0
    r=tp/(tp+fn) if tp+fn else 1.0
    f=2*p*r/(p+r) if p+r else 0.0
    return {"tp":tp,"fp":fp,"fn":fn,"precision":p,"recall":r,"f1":f}

def mtext(m):
    return f"P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} (TP={m['tp']} FP={m['fp']} FN={m['fn']})"

def overlap(a,b):
    if a["page_number"]!=b["page_number"]: return 0.0
    x=max(a["start"],b["start"]); y=min(a["end"],b["end"])
    return max(0,y-x)/max(1,a["end"]-a["start"])

def gitsha():
    try:
        return subprocess.run(["git","rev-parse","HEAD"],check=True,capture_output=True,text=True).stdout.strip()
    except Exception:
        return "unknown"

def main():
    cases=build_cases()
    base=get_profile("general_business")
    profile=replace(base,entities=entities_for_scope(base,"maximum"))
    service=PrivacyGateService()
    total=Counter(); groups=defaultdict(Counter); entities=defaultdict(Counter); rows=[]; cat_hits=0
    for c in cases:
        doc=AnalysisDocument(source_kind="text",pages=(PageContent(page_number=1,text=c["text"]),))
        findings=service.analyze(doc,profile,language="en")
        pred=[{"entity_type":str(x.entity_type),"value":str(x.text),"page_number":int(x.page_number),"start":int(x.start),"end":int(x.end),"score":float(x.score)} for x in findings]
        ek={(e["page_number"],e["start"],e["end"],e["entity_type"]):e for e in c["expected"]}
        pk={(p["page_number"],p["start"],p["end"],p["entity_type"]):p for p in pred}
        exact=ek.keys() & pk.keys()
        misses=[e for k,e in ek.items() if k not in pk]
        extras=[p for k,p in pk.items() if k not in ek]
        tp,fp,fn=len(exact),len(extras),len(misses)
        perfect=tp==len(ek) and fp==0 and fn==0
        negative=not ek; clean=negative and not pred
        total.update(cases=1,expected=len(ek),tp=tp,fp=fp,fn=fn,perfect=int(perfect),negative=int(negative),negative_clean=int(clean))
        g=groups[c["group"]]; g.update(cases=1,expected=len(ek),tp=tp,fp=fp,fn=fn,perfect=int(perfect),negative=int(negative),negative_clean=int(clean))
        for e in c["expected"]:
            name=e["entity_type"]; entities[name]["expected"]+=1
            key=(e["page_number"],e["start"],e["end"],name)
            if key in pk: entities[name]["tp"]+=1
            else: entities[name]["fn"]+=1
            if any(p["entity_type"]==name and overlap(e,p)>=RELAXED_OVERLAP for p in pred): cat_hits+=1
        for p in extras: entities[p["entity_type"]]["fp"]+=1
        rows.append({"case_id":c["id"],"group":c["group"],"tp":tp,"fp":fp,"fn":fn,"perfect":perfect,"negative_clean":clean if negative else "","expected":json.dumps(c["expected"],ensure_ascii=False),"predictions":json.dumps(pred,ensure_ascii=False),"misses":json.dumps(misses,ensure_ascii=False),"extras":json.dumps(extras,ensure_ascii=False)})
    OUT_CSV.parent.mkdir(parents=True,exist_ok=True)
    with OUT_CSV.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    strict=metric(total["tp"],total["fp"],total["fn"])
    overlap_recall=cat_hits/total["expected"] if total["expected"] else 1.0
    summary={"git_sha":gitsha(),"cases":total["cases"],"expected_spans":total["expected"],"negative_cases":total["negative"],"strict":strict,"correct_category_overlap_recall":overlap_recall,"perfect_cases":total["perfect"],"negative_clean":total["negative_clean"],"by_group":{},"by_entity":{}}
    for name,b in sorted(groups.items()):
        summary["by_group"][name]={"cases":b["cases"],"expected":b["expected"],**metric(b["tp"],b["fp"],b["fn"]),"perfect":b["perfect"],"negative":b["negative"],"negative_clean":b["negative_clean"]}
    for name,b in sorted(entities.items()):
        summary["by_entity"][name]={"expected":b["expected"],**metric(b["tp"],b["fp"],b["fn"])}
    OUT_JSON.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("PrivacyGate English blind validation v1")
    print(f"Cases: {total['cases']}")
    print(f"Expected spans: {total['expected']}")
    print(f"Negative/adversarial cases: {total['negative']}")
    print(f"Strict exact: {mtext(strict)}")
    print(f"Correct-category overlap recall: {overlap_recall:.3f}")
    print(f"Perfect cases: {total['perfect']}/{total['cases']}")
    print(f"Negative clean: {total['negative_clean']}/{total['negative']} ({total['negative_clean']/total['negative']:.3f})")
    print(f"CSV: {OUT_CSV}"); print(f"Summary: {OUT_JSON}")
    print("\nBy group:")
    for name,d in summary["by_group"].items():
        suffix=f" negative-clean={d['negative_clean']}/{d['negative']}" if d["negative"] else ""
        print(f"  {name:22s} cases={d['cases']:3d} {mtext(d)}{suffix}")
    probs=[(n,d) for n,d in summary["by_entity"].items() if d["fp"] or d["fn"]]
    if probs:
        print("\nEntities with misses or false positives:")
        for n,d in probs: print(f"  {n:32s} {mtext(d)}")
    else:
        print("\nNo entity-level misses or false positives.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
