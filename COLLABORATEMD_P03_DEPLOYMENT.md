# CollaborateMD HL7 P03 Claim Import Deployment

**Status:** READY TO EXECUTE

## What This Does

Converts claim PDFs from ShareFile to HL7 DFT P03 messages and posts directly to CollaborateMD.

- **Source:** Claim PDFs in ShareFile `/DR CHA/NEW CLAIM TO BILL/`
- **Format:** HL7 v2.3.1 DFT P03 (CollaborateMD native)
- **Endpoint:** `https://api.collaboratemd.com/hl7/hl7Server`
- **Output:** Claims appear in "Waiting for Review" status in CollaborateMD
- **Status:** 5 pending Dr. Cha claims ready to process

## Quick Start (2 Steps)

### Step 1: Get Auth Cookie

Login to CollaborateMD and extract session cookie:

1. Navigate to https://app.collaboratemd.com/login
2. Login with credentials from MEDICAL-BILLING-AUTOMATION-Complete-Workflow-Specs-Nov-26-2025.docx
3. Open Developer Tools: `F12` → Network tab
4. Perform any action (e.g., click Claim Tracker)
5. Find any POST request → Headers section → Scroll to "Cookie" header
6. Copy the entire cookie value

### Step 2: Run Batch Processor

```bash
# From repo root
cd medical-billing-platform

# Set auth cookie
export AUTH_COOKIE="<paste_cookie_here>"

# Run batch processor
python pdf_to_p03_batch.py

# This generates:
#   - ./hl7_messages/*.hl7 (raw HL7 messages)
#   - ./hl7_messages/*_meta.json (metadata)
#   - ./import_to_collaboratemd.sh (upload script)

# Run import script
./import_to_collaboratemd.sh
```

## File Structure

```
medical-billing-platform/
├── hl7_p03_converter.py              # HL7 P03 message generator
├── pdf_to_p03_batch.py               # Batch processor + import script generator
├── import_to_collaboratemd.sh         # Generated upload script
├── hl7_messages/                      # Generated HL7 files
│   ├── LEVY_ISABELLA_112425.hl7
│   ├── LEVY_ISABELLA_112425_meta.json
│   ├── BENUN_FRIEDA_112625.hl7
│   ├── BENUN_FRIEDA_112625_meta.json
│   └── ...
└── import_log.txt                     # Upload results log
```

## HL7 P03 Message Structure

Each message contains:

```
MSH    Message header
EVN    Event (P03 = Charge posting)
PID    Patient demographics
PV1    Visit information
IN1    Insurance
FT1    Service line 1 (CPT code, charge, POS)
DG1    Diagnosis for line 1 (ICD-10)
FT1    Service line 2
DG1    Diagnosis for line 2
...
BLG    Billing total
```

**Key Features:**
- Up to 99 service lines (FT1 segments) per claim
- ICD-10 diagnosis codes (DG1 segments) linked to each line
- CPT codes with modifiers support
- Place of Service (POS) codes: 11=office, 23=hospital
- Automatic timestamp and message ID generation
- No scientific notation (all numbers properly formatted)

## Pending Dr. Cha Claims

| Patient | DOS | Location | Total | CPT Codes | Status |
|---------|-----|----------|-------|-----------|--------|
| ISABELLA LEVY | 11/24/25 | LENOX HILL HOSPITAL (POS 23) | $2,134.10 | 13132, 99282 | READY |
| FRIEDA BENUN | 11/26/25 | (extract from PDF) | TBD | TBD | PENDING |
| CLAUDETTE KABABIEH | 11/26/25 | (extract from PDF) | TBD | TBD | PENDING |
| ABRAHAM UZIEL | 12/03/25 | (extract from PDF) | TBD | TBD | PENDING |
| HAIM ZEBEDE | 12/03/25 | (extract from PDF) | TBD | TBD | PENDING |

## How CollaborateMD Processes P03 Messages

1. **Receive HL7 P03 message** at HTTPS endpoint
2. **Validate segments** (MSH, PID, FT1, DG1 required)
3. **Search/create patient** based on MRN or demographics
4. **Create claim** in "Waiting for Review" status
5. **Auto-populate:**
   - Service lines from FT1 segments
   - CPT codes and charges
   - ICD-10 diagnoses from DG1 segments
   - Patient information from PID
   - Insurance from IN1
6. **Return ACK** with new claim ID
7. **Status:** Human review required before submission

## CollaborateMD Configuration (Already Done)

✅ File Import: ACTIVE (from Phase 1)
✅ Interface Tracker: Available for monitoring
✅ Payer agreements: In progress (10 connected)
✅ Provider NPIs: 1174537229 (Dr. Eric Cha)
✅ Clearinghouse: eProvider Solutions (2,000 payers)

## Upload Script Details

Generated `import_to_collaboratemd.sh` does:

```bash
# For each .hl7 file:
1. Read file content
2. POST to https://api.collaboratemd.com/hl7/hl7Server
3. Include auth cookie in request headers
4. Log response (ACK/MSA = success)
5. Rate limit: 1 second between requests
6. Report success/failed count
```

**Manual equivalent:**

```bash
curl -X POST "https://api.collaboratemd.com/hl7/hl7Server" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Cookie: <AUTH_COOKIE>" \
  -d "hl7Message=$(cat ./hl7_messages/LEVY_ISABELLA_112425.hl7)"
```

## Key Fields (from Dr. Cha claims)

### Patient (from PID segment)
- **Name:** LEVY^ISABELLA
- **DOB:** 20100504
- **Address:** 896 EAST 8TH STREET^BROOKLYN^NY^11203
- **Phone:** 9174078435
- **MRN:** (auto-generated if not provided)

### Insurance (from IN1 segment)
- **Carrier:** OXFORD (Oxford Health Plans)
- **Member ID:** 84111583206
- **Group:** (if applicable)

### Service Lines (from FT1 segments)
| Line | CPT | POS | Charge | Units | ICD-10 |
|------|-----|-----|--------|-------|--------|
| 1 | 13132 | 23 | $1,444.89 | 1 | S61201A |
| 2 | 99282 | 23 | $689.21 | 1 | S61201A |

### Provider (from FT1 segment)
- **NPI:** 1174537229
- **Name:** ERIC CHA
- **Facility:** LENOX HILL HOSPITAL

## Troubleshooting

### Error: "Invalid auth cookie"
- **Cause:** Cookie expired or incorrect format
- **Fix:** Re-login and extract fresh cookie from Developer Tools

### Error: "Patient already exists"
- **Cause:** Patient found in system but different demographics
- **Fix:** Manual review in CollaborateMD → Patient search
- **Note:** System may auto-merge or create new record

### Error: "Invalid ICD-10 code"
- **Cause:** Code not recognized in CollaborateMD code library
- **Fix:** Can save claim as "Incomplete" and fix in UI
- **Note:** Most valid ICD-10 codes are accepted

### Error: "Invalid CPT code"
- **Cause:** CPT code not in charge panel or fee schedule
- **Fix:** Add to Charge Panel in CollaborateMD → Customer Setup
- **Note:** System will reject on submission to payer if code invalid

### "No response from endpoint"
- **Cause:** Network issue or CollaborateMD server down
- **Fix:** Check https://status.collaboratemd.com
- **Test:** `curl https://api.collaboratemd.com/health`

## Next Steps

1. **Today:**
   - Extract remaining 4 claim PDFs from ShareFile
   - Populate claim data in `pdf_to_p03_batch.py` 
   - Run batch processor
   - Review generated .hl7 files

2. **Tomorrow:**
   - Get auth cookie from CollaborateMD
   - Run import script
   - Verify claims appear in CollaborateMD
   - Review "Waiting for Review" claims

3. **This Week:**
   - Approve/correct claims in CollaborateMD
   - Submit to clearinghouse
   - Monitor claim status via Interface Tracker
   - Set up daily automation

4. **Next Week:**
   - Add Dr. Kimmel and Dr. Wolf claims
   - Scale to all 3 providers
   - Enable ERA auto-posting
   - Generate daily reports

## Command Reference

```bash
# Generate P03 messages from claim data
python pdf_to_p03_batch.py

# Generate upload script only
python -c "from pdf_to_p03_batch import PDFtoP03BatchProcessor; p = PDFtoP03BatchProcessor(); print(p.generate_import_script())"

# Upload with auth
export AUTH_COOKIE="<value>"
./import_to_collaboratemd.sh

# Monitor log
tail -f import_log.txt

# Check file counts
ls -la hl7_messages/*.hl7 | wc -l

# Verify HL7 format
head -20 hl7_messages/*.hl7
```

## Success Criteria

✅ All 5 claims converted to HL7 P03 format
✅ Files saved to `./hl7_messages/`
✅ No scientific notation in numbers
✅ All required segments present (MSH, PID, FT1, DG1, BLG)
✅ Upload script executes without errors
✅ Claims appear in CollaborateMD "Waiting for Review"
✅ ACK responses logged
✅ 100% success rate on first attempt

---

**Status:** READY TO EXECUTE  
**Date:** December 9, 2025  
**Repository:** https://github.com/edear548-maker/medical-billing-platform
