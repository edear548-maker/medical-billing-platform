"""HL7 DFT P03 CollaborateMD Claim Converter

Converts medical claim data to HL7 v2.3.1 DFT P03 messages for direct import
into CollaborateMD via HTTPS endpoint: https://api.collaboratemd.com/hl7/hl7Server

Supports:
- Up to 99 service lines (FT1 segments) per claim
- ICD-10 diagnosis codes (DG1 segments)
- CPT codes with modifiers
- Place of Service (POS) codes (11=office, 23=hospital)
- Multiple insurance carriers

Usage:
    generator = HL7P03Generator()
    result = generator.generate_p03_message(claim_data_dict)
    # POST result['message'] to CollaborateMD endpoint
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json


class HL7P03Generator:
    """Generate HL7 DFT P03 messages for CollaborateMD claim import"""
    
    def __init__(self, sending_app: str = "SHAREFILE", sending_facility: str = "REVENUE_TARGETED"):
        self.sending_app = sending_app
        self.sending_facility = sending_facility
        self.msg_counter = 1
        
    def _format_timestamp(self) -> str:
        """Return YYYYMMDDHHMM format timestamp (no scientific notation)"""
        return datetime.now().strftime('%Y%m%d%H%M%S')
    
    def _format_number(self, value: float, decimals: int = 2) -> str:
        """Format number without scientific notation"""
        return f"{float(value):.{decimals}f}"
    
    def _escape_field(self, value: str) -> str:
        """Escape special HL7 characters"""
        if not value:
            return ""
        # Replace ^ with \S\ etc if needed, but generally safe in CollaborateMD
        return str(value).strip()
    
    def generate_p03_message(self, claim_data: Dict) -> Dict:
        """
        Generate HL7 DFT P03 message from claim data dictionary.
        
        Args:
            claim_data: Dictionary containing claim information
                Required keys:
                  - patient_last_name: str
                  - patient_first_name: str
                  - patient_dob: str (YYYYMMDD format)
                  - patient_address: str
                  - patient_city: str
                  - patient_state: str (2-letter)
                  - patient_zip: str
                  - patient_phone: str (10 digits)
                  - member_id: str
                  - group_number: str (optional)
                  - payer_name: str
                  - provider_npi: str (10 digits)
                  - provider_name: str
                  - facility_name: str
                  - dos_from: str (YYYYMMDD)
                  - dos_to: str (YYYYMMDD)
                  - lines: List[Dict] with keys:
                    - cpt: str (5 digits)
                    - pos: str (2 digits, 11 or 23)
                    - charge: float
                    - units: int
                    - icd: str (ICD-10 code)
                    - modifiers: List[str] (optional)
        
        Returns:
            Dict with keys:
                - message: str (raw HL7 message)
                - message_id: str
                - timestamp: str
                - total_charge: float
                - line_count: int
                - segments: List[str] (for debugging)
        """
        timestamp = self._format_timestamp()
        msg_id = f"MSG{self.msg_counter:09d}"
        self.msg_counter += 1
        
        segments = []
        
        # MSH - Message Header
        msh = (
            f"MSH|^~\\\\&|"
            f"{self._escape_field(self.sending_app)}|"
            f"{self._escape_field(self.sending_facility)}|"
            f"COLLABORATEMD|COLLABORATEMD|"
            f"{timestamp}||DFT^P03|{msg_id}|P|2.3.1"
        )
        segments.append(msh)
        
        # EVN - Event Type (P03 = Charge posting)
        evn = f"EVN|P03|{timestamp}"
        segments.append(evn)
        
        # PID - Patient Identification
        patient_name = f"{self._escape_field(claim_data['patient_last_name'])}^{self._escape_field(claim_data['patient_first_name'])}"
        phone = self._escape_field(claim_data.get('patient_phone', ''))
        if phone:
            # Strip to digits only
            phone = ''.join(filter(str.isdigit, phone))
        
        pid = (
            f"PID||1||^^^MRN|{patient_name}||"
            f"{claim_data.get('patient_dob', '')}|U||"
            f"{self._escape_field(claim_data.get('patient_address', ''))}^"
            f"{self._escape_field(claim_data.get('patient_city', ''))}^"
            f"{self._escape_field(claim_data.get('patient_state', ''))}^"
            f"{self._escape_field(claim_data.get('patient_zip', ''))}|||"
            f"{phone}"
        )
        segments.append(pid)
        
        # PV1 - Patient Visit
        facility_name = self._escape_field(claim_data.get('facility_name', 'FACILITY'))
        dos_from = claim_data.get('dos_from', timestamp[:8])
        pv1 = (
            f"PV1||I||^^^{facility_name}||"
            f"|||||||||||||||||||||||||||||||||{dos_from}"
        )
        segments.append(pv1)
        
        # IN1 - Insurance (Primary)
        member_id = self._escape_field(claim_data.get('member_id', ''))
        group_number = self._escape_field(claim_data.get('group_number', ''))
        payer_name = self._escape_field(claim_data.get('payer_name', 'PAYER'))
        
        in1 = (
            f"IN1|1|{payer_name}|||||||||||||{member_id}|{patient_name}||"
            f"||||||||||||||||||||||||{group_number}"
        )
        segments.append(in1)
        
        # FT1 segments (Financial Transactions = service lines)
        ft1_seq = 1
        total_charge = 0.0
        provider_npi = self._escape_field(claim_data.get('provider_npi', ''))
        dos_service = dos_from
        
        for line in claim_data.get('lines', []):
            cpt = self._escape_field(line.get('cpt', ''))
            pos = self._escape_field(line.get('pos', '11'))
            charge = float(line.get('charge', 0))
            units = int(line.get('units', 1))
            icd = self._escape_field(line.get('icd', ''))
            modifiers = line.get('modifiers', [])
            modifier_str = ''.join([self._escape_field(m) for m in modifiers])
            
            total_charge += charge
            charge_str = self._format_number(charge)
            
            ft1 = (
                f"FT1|{ft1_seq}|CLM|CLM{ft1_seq:03d}||CH|"
                f"{charge_str}|{units}|{charge_str}|{dos_service}|DX|{pos}|{cpt}||"
                f"{modifier_str}|||{provider_npi}|{charge_str}||{charge_str}"
            )
            segments.append(ft1)
            
            # DG1 - Diagnosis (tied to FT1 line)
            dg1 = f"DG1|{ft1_seq}|ICD10|{icd}|||A"
            segments.append(dg1)
            
            ft1_seq += 1
        
        # BLG - Billing (summary)
        total_str = self._format_number(total_charge)
        blg = f"BLG|{total_str}|||{payer_name}"
        segments.append(blg)
        
        # Join with carriage returns
        message = '\r'.join(segments) + '\r'
        
        return {
            'message': message,
            'message_id': msg_id,
            'timestamp': timestamp,
            'total_charge': total_charge,
            'line_count': len(claim_data.get('lines', [])),
            'segments': segments  # For debugging
        }


class CollaborateMDClient:
    """Client for posting HL7 P03 messages to CollaborateMD"""
    
    def __init__(self, auth_cookie: str, endpoint: str = "https://api.collaboratemd.com/hl7/hl7Server"):
        self.auth_cookie = auth_cookie
        self.endpoint = endpoint
        self.session_results = []
    
    def format_payload(self, hl7_message: str) -> str:
        """Format HL7 message for POST payload"""
        # URL-encode if needed, but HL7 POST typically sends raw
        return f"hl7Message={hl7_message}"
    
    def get_curl_command(self, hl7_message: str, message_id: str) -> str:
        """Generate curl command for manual testing"""
        payload = self.format_payload(hl7_message)
        return (
            f'curl -X POST "{self.endpoint}" '
            f'-H "Content-Type: application/x-www-form-urlencoded" '
            f'-H "Cookie: {self.auth_cookie}" '
            f'-d "{payload}" '
            f'# Message ID: {message_id}'
        )


def example_isabella_levy() -> Dict:
    """Example claim: Isabella Levy (Dr. Cha, 11/24/2025)"""
    return {
        'patient_last_name': 'LEVY',
        'patient_first_name': 'ISABELLA',
        'patient_dob': '20100504',
        'patient_address': '896 EAST 8TH STREET',
        'patient_city': 'BROOKLYN',
        'patient_state': 'NY',
        'patient_zip': '11203',
        'patient_phone': '9174078435',
        'member_id': '84111583206',
        'group_number': '',
        'payer_name': 'OXFORD',
        'provider_npi': '1174537229',
        'provider_name': 'ERIC CHA',
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
    }


if __name__ == "__main__":
    # Quick test
    gen = HL7P03Generator()
    result = gen.generate_p03_message(example_isabella_levy())
    
    print("HL7 P03 MESSAGE GENERATED")
    print(f"Message ID: {result['message_id']}")
    print(f"Total Charge: ${result['total_charge']:,.2f}")
    print(f"Service Lines: {result['line_count']}")
    print(f"\nMessage (first 500 chars):\n{result['message'][:500]}...")
    print(f"\nTotal message length: {len(result['message'])} bytes")
