"""PDF-to-HL7 P03 Batch Processor for ShareFile Claims

Processes multiple claim PDFs and converts to HL7 DFT P03 messages
for CollaborateMD bulk import.

Usage:
    python pdf_to_p03_batch.py --input-dir ./claims --output-dir ./hl7_messages
    python pdf_to_p03_batch.py --claims claims.json  # From JSON data
"""

import json
import os
from typing import List, Dict, Optional
from pathlib import Path
from hl7_p03_converter import HL7P03Generator


class PDFtoP03BatchProcessor:
    """Batch process claim data to HL7 P03 messages"""
    
    def __init__(self, output_dir: str = "./hl7_messages"):
        self.generator = HL7P03Generator()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.errors = []
    
    def process_claim_dict(self, claim_data: Dict, claim_id: str) -> bool:
        """Process single claim dictionary to P03 message file
        
        Args:
            claim_data: Claim dictionary
            claim_id: Unique claim identifier for filename
        
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.generator.generate_p03_message(claim_data)
            
            # Save raw HL7 message
            hl7_file = self.output_dir / f"{claim_id}.hl7"
            with open(hl7_file, 'w') as f:
                f.write(result['message'])
            
            # Save metadata JSON
            meta_file = self.output_dir / f"{claim_id}_meta.json"
            with open(meta_file, 'w') as f:
                json.dump({
                    'claim_id': claim_id,
                    'message_id': result['message_id'],
                    'timestamp': result['timestamp'],
                    'total_charge': result['total_charge'],
                    'line_count': result['line_count'],
                    'hl7_file': str(hl7_file),
                    'status': 'ready_for_import'
                }, f, indent=2)
            
            self.results.append({
                'claim_id': claim_id,
                'status': 'success',
                'file': str(hl7_file),
                'message_id': result['message_id'],
                'charge': result['total_charge'],
                'lines': result['line_count']
            })
            
            return True
            
        except Exception as e:
            error_msg = f"Error processing {claim_id}: {str(e)}"
            self.errors.append(error_msg)
            self.results.append({
                'claim_id': claim_id,
                'status': 'error',
                'error': str(e)
            })
            return False
    
    def process_batch(self, claims: List[Dict]) -> Dict:
        """Process batch of claims
        
        Args:
            claims: List of claim dictionaries
        
        Returns:
            Summary dict with success/failure counts
        """
        success_count = 0
        fail_count = 0
        
        for i, claim in enumerate(claims, 1):
            claim_id = claim.get('claim_id') or f"CLAIM_{i:04d}"
            if self.process_claim_dict(claim, claim_id):
                success_count += 1
            else:
                fail_count += 1
        
        return {
            'total': len(claims),
            'success': success_count,
            'failed': fail_count,
            'success_rate': f"{100 * success_count / len(claims):.1f}%" if claims else "0%",
            'output_dir': str(self.output_dir),
            'errors': self.errors,
            'results': self.results
        }
    
    def generate_import_script(self) -> str:
        """Generate bash script to upload all HL7 messages to CollaborateMD
        
        Returns:
            Bash script content
        """
        script = "#!/bin/bash\n"
        script += "# Generated CollaborateMD HL7 P03 Import Script\n\n"
        script += "# Configuration\n"
        script += "ENDPOINT='https://api.collaboratemd.com/hl7/hl7Server'\n"
        script += "AUTH_COOKIE=''  # Set from CollaborateMD login session\n"
        script += "OUTPUT_DIR='./hl7_messages'\n"
        script += "LOG_FILE='./import_log.txt'\n\n"
        
        script += "# Check if auth cookie is set\n"
        script += "if [ -z \"$AUTH_COOKIE\" ]; then\n"
        script += "  echo 'ERROR: AUTH_COOKIE not set'\n"
        script += "  echo 'Instructions:'\n"
        script += "  echo '1. Login to CollaborateMD at https://app.collaboratemd.com/login'\n"
        script += "  echo '2. Open Developer Tools (F12) -> Network tab'\n"
        script += "  echo '3. Look for any POST request'\n"
        script += "  echo '4. Copy the Cookie header value'\n"
        script += "  echo '5. Set: export AUTH_COOKIE=\"value\"'\n"
        script += "  exit 1\n"
        script += "fi\n\n"
        
        script += "# Process each .hl7 file\n"
        script += "success=0\n"
        script += "failed=0\n\n"
        
        script += "for file in $OUTPUT_DIR/*.hl7; do\n"
        script += "  if [ -f \"$file\" ]; then\n"
        script += "    filename=$(basename \"$file\")\n"
        script += "    message=$(cat \"$file\")\n"
        script += "    echo \"[$(date)] Processing $filename...\" | tee -a \"$LOG_FILE\"\n"
        script += "    \n"
        script += "    response=$(curl -s -X POST \"$ENDPOINT\" \\\n"
        script += "      -H 'Content-Type: application/x-www-form-urlencoded' \\\n"
        script += "      -H \"Cookie: $AUTH_COOKIE\" \\\n"
        script += "      -d \"hl7Message=$message\")\n"
        script += "    \n"
        script += "    if echo \"$response\" | grep -q 'ACK\|MSA'; then\n"
        script += "      echo \"  SUCCESS: $response\" | tee -a \"$LOG_FILE\"\n"
        script += "      ((success++))\n"
        script += "    else\n"
        script += "      echo \"  FAILED: $response\" | tee -a \"$LOG_FILE\"\n"
        script += "      ((failed++))\n"
        script += "    fi\n"
        script += "    \n"
        script += "    sleep 1  # Rate limiting\n"
        script += "  fi\n"
        script += "done\n\n"
        
        script += "echo \"" | tee -a \"$LOG_FILE\"\n"
        script += "echo \"=== IMPORT COMPLETE ===\" | tee -a \"$LOG_FILE\"\n"
        script += "echo \"Success: $success | Failed: $failed\" | tee -a \"$LOG_FILE\"\n"
        
        return script


def dr_cha_claims_data() -> List[Dict]:
    """Dr. Cha pending claims from ShareFile (manual extraction)
    
    Format extrapolated from your workflow docs:
    - BENUN, FRIEDA (11/26/2025)
    - KABABIEH, CLAUDETTE (11/26/2025)
    - LEVY, ISABELLA (11/24/2025) - already processed
    - UZIEL, ABRAHAM (12/03/2025)
    - ZEBEDE, HAIM (12/03/2025)
    """
    
    claims = [
        {
            'claim_id': 'LEVY_ISABELLA_112425',
            'patient_last_name': 'LEVY',
            'patient_first_name': 'ISABELLA',
            'patient_dob': '20100504',
            'patient_address': '896 EAST 8TH STREET',
            'patient_city': 'BROOKLYN',
            'patient_state': 'NY',
            'patient_zip': '11203',
            'patient_phone': '9174078435',
            'member_id': '84111583206',
            'payer_name': 'OXFORD',
            'provider_npi': '1174537229',
            'facility_name': 'LENOX HILL HOSPITAL',
            'dos_from': '20251124',
            'dos_to': '20251124',
            'lines': [
                {
                    'cpt': '13132',
                    'pos': '23',
                    'charge': 1444.89,
                    'units': 1,
                    'icd': 'S61201A',
                    'modifiers': []
                },
                {
                    'cpt': '99282',
                    'pos': '23',
                    'charge': 689.21,
                    'units': 1,
                    'icd': 'S61201A',
                    'modifiers': []
                }
            ]
        },
                {
            'claim_id': 'BENUN_FRIEDA_112625',
            'patient_last_name': 'BENUN',
            'patient_first_name': 'FRIEDA',
            'patient_dob': '19901212',
            'patient_address': '1573 EAST 4TH ST',
            'patient_city': 'BROOKLYN',
            'patient_state': 'NY',
            'patient_zip': '11230',
            'patient_phone': '7329774869',
            'member_id': '989430625',
            'payer_name': 'UNITED HEALTHCARE',
            'provider_npi': '1174537229',
            'facility_name': 'LENOX HILL HOSPITAL',
            'dos_from': '20251126',
            'dos_to': '20251126',
            'lines': [
                {
                    'cpt': '14040',
                    'pos': '23',
                    'charge': 26787.98,
                    'units': 1,
                    'icd': 'S86120A',
                    'modifiers': []
                },
                {
                    'cpt': '99282',
                    'pos': '23',
                    'charge': 689.21,
                    'units': 1,
                    'icd': 'S86120A',
                    'modifiers': []
                }
            ]
        },
        {
            'claim_id': 'UZIEL_ABRAHAM_120325',
            'patient_last_name': 'UZIEL',
            'patient_first_name': 'ABRAHAM',
            'patient_dob': '20130929',
            'patient_address': '1643 EAST 3RD STREET',
            'patient_city': 'BROOKLYN',
            'patient_state': 'NY',
            'patient_zip': '11230',
            'patient_phone': '9174762183',
            'member_id': '11914589603',
            'payer_name': 'OXFORD',
            'provider_npi': '1174537229',
            'facility_name': 'LENOX HILL HOSPITAL',
            'dos_from': '20251202',
            'dos_to': '20251202',
            'lines': [
                {
                    'cpt': '13132',
                    'pos': '23',
                    'charge': 14445.89,
                    'units': 1,
                    'icd': 'S86120A',
                    'modifiers': []
                },
                {
                    'cpt': '99282',
                    'pos': '23',
                    'charge': 689.21,
                    'units': 1,
                    'icd': 'S86120A',
                    'modifiers': []
                }
            ]
        }
        # Placeholder for remaining 4 PDFs - populate from ShareFile extraction
    ]
    
    return claims


if __name__ == "__main__":
    import sys
    
    # Quick test with Dr. Cha claims
    processor = PDFtoP03BatchProcessor(output_dir="./hl7_messages")
    
    print("\n" + "="*80)
    print("HL7 P03 BATCH PROCESSOR - DR. CHA CLAIMS")
    print("="*80 + "\n")
    
    claims = dr_cha_claims_data()
    print(f"Processing {len(claims)} claim(s)...\n")
    
    summary = processor.process_batch(claims)
    
    print(f"Results: {summary['success']}/{summary['total']} successful ({summary['success_rate']})")
    
    if summary['errors']:
        print("\nErrors:")
        for error in summary['errors']:
            print(f"  - {error}")
    
    print(f"\nOutput directory: {summary['output_dir']}")
    print("\nGenerated files:")
    for result in summary['results']:
        if result['status'] == 'success':
            print(f"  ✓ {result['claim_id']}: ${result['charge']:,.2f} ({result['lines']} lines)")
        else:
            print(f"  ✗ {result['claim_id']}: {result.get('error', 'unknown error')}")
    
    # Generate import script
    print("\nGenerating import script...")
    import_script = processor.generate_import_script()
    script_file = Path("./import_to_collaboratemd.sh")
    with open(script_file, 'w') as f:
        f.write(import_script)
    os.chmod(script_file, 0o755)
    print(f"  Script saved: {script_file}")
    print("  Run: ./import_to_collaboratemd.sh")
    
    print("\n" + "="*80 + "\n")
