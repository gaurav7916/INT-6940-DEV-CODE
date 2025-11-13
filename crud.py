from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from models import *
from schemas import *
from datetime import datetime
from typing import Tuple, Dict, Any
import random
import string

def start_appointment(
    db: Session,
    request: AppointmentStartRequest
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Start an appointment by updating queue ticket status
    """
    try:
        # print(f"Ticket ID: {request.ticket_id}")
        # Step 1: Find queue ticket
        ticket = db.query(QueueTicket).filter(
            QueueTicket.ticket_id == request.ticket_id
        ).first()
        
        if not ticket:
            # print(f"Ticket #{request.ticket_id} not found")
            return False, "Queue ticket not found", {}
        
        # print(f"Found ticket #{ticket.ticket_id}")
        # print(f"   Current status: {ticket.queue_status}")
        
        # Step 2: Validate current status
        if ticket.queue_status not in ['WAITING', 'CALLED']:
            # print(f"Invalid status: {ticket.queue_status}")
            return False, f"Cannot start appointment. Current status: {ticket.queue_status}", {}
        
        # Step 3: Get visit details
        visit = db.query(Visit).filter(
            Visit.visit_id == ticket.visit_id
        ).first()
        
        if not visit:
            # print(f"Visit #{ticket.visit_id} not found")
            return False, "Visit not found", {}
        
        # print(f"Found visit #{visit.visit_id}")
        
        # Step 4: Get patient details
        patient = db.query(Patient).filter(
            Patient.patient_id == visit.patient_id
        ).first()
        
        if not patient:
            # print(f"Patient #{visit.patient_id} not found")
            return False, "Patient not found", {}
        
        patient_name = f"{patient.first_name} {patient.last_name}"
        # print(f"Found patient: {patient_name}")
        
        # Step 5: Update queue ticket
        old_status = ticket.queue_status
        ticket.queue_status = 'IN_PROGRESS'
        ticket.started_at = datetime.utcnow()
        ticket.updated_at = datetime.utcnow()
        
        # Step 6: Update visit status
        visit.visit_status = 'IN_PROGRESS'
        visit.updated_at = datetime.utcnow()
        
        # Step 7: Commit changes
        db.commit()
        
        # print(f"Status updated: {old_status} → IN_PROGRESS")
        # print(f"Started at: {ticket.started_at}")
        
        return True, "Appointment started successfully", {
            "ticket_id": ticket.ticket_id,
            "visit_id": visit.visit_id,
            "patient_name": patient_name,
            "queue_status": ticket.queue_status,
            "started_at": ticket.started_at
        }
        
    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")
        return False, f"Error starting appointment: {str(e)}", {}


def verify_otp_and_checkin(
    db: Session,
    request: OTPVerifyRequest
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Verify OTP and complete check-in process
    """
    try:
        # print(f"Phone: {request.phone_number}")
        # print(f"Code: {request.otp_code}")
        
        # Step 1: Find valid OTP
        otp_record = db.query(OTPVerification).filter(
            and_(
                OTPVerification.phone_number == request.phone_number,
                OTPVerification.otp_code == request.otp_code,
                OTPVerification.is_verified == False,
                OTPVerification.is_expired == False,
                OTPVerification.expires_at > func.now()
            )
        ).first()
        
        if not otp_record:
            return False, "Invalid or expired OTP", {}
        
        print(f"Found valid OTP: {otp_record.otp_id}")
        
        # Step 2: Check retry attempts
        if otp_record.retry_count >= otp_record.max_attempts:
            otp_record.is_expired = True
            db.commit()
            return False, "Maximum OTP verification attempts exceeded", {}
        
        # Step 3: Verify patient exists
        patient = db.query(Patient).filter(
            Patient.patient_id == otp_record.patient_id
        ).first()
        
        if not patient:
            return False, "Patient not found", {}
        
        # print(f"Patient: {patient.first_name} {patient.last_name}")
        
        # Step 4: Mark OTP as verified
        otp_record.is_verified = True
        otp_record.verified_at = datetime.utcnow()
        otp_record.updated_at = datetime.utcnow()
        
        # Step 5: Check if patient already checked in today
        today = datetime.utcnow().date()
        existing_visit = db.query(Visit).filter(
            and_(
                Visit.patient_id == patient.patient_id,
                Visit.visit_date == today,
                Visit.visit_status.in_(['ACTIVE', 'WAITING', 'IN_PROGRESS'])
            )
        ).first()
        
        if existing_visit:
            queue_ticket = db.query(QueueTicket).filter(
                QueueTicket.visit_id == existing_visit.visit_id
            ).first()
            
            db.commit()
            
            return True, "Already checked in for today", {
                "patient_id": patient.patient_id,
                "visit_id": existing_visit.visit_id,
                "ticket_id": queue_ticket.ticket_id if queue_ticket else None,
                "queue_position": queue_ticket.queue_position if queue_ticket else None,
                "estimated_wait_time": queue_ticket.estimated_wait_time if queue_ticket else None
            }
        
        # Step 6: Create new visit
        new_visit = Visit(
            patient_id=patient.patient_id,
            department_id=request.department_id,
            doctor_id=request.doctor_id,
            visit_date=today,
            check_in_datetime=datetime.utcnow(),
            check_in_method=request.check_in_method,
            visit_status='ACTIVE'
        )
        db.add(new_visit)
        db.flush()
        
        # print(f"Created visit #{new_visit.visit_id}")
        
        # Step 7: Calculate queue position
        max_position = db.query(func.max(QueueTicket.queue_position)).filter(
            and_(
                QueueTicket.queue_date == today,
                QueueTicket.queue_status.in_(['WAITING', 'CALLED', 'IN_PROGRESS'])
            )
        ).scalar() or 0
        
        new_position = max_position + 1
        
        # Step 8: Get department info for wait time
        department = db.query(Department).filter(
            Department.department_id == request.department_id
        ).first()
        
        average_service_time = department.average_service_time if department else 30
        estimated_wait = (new_position - 1) * average_service_time
        
        # print(f"Queue position: {new_position}")
        # print(f"Estimated wait: {estimated_wait} minutes")
        
        # Step 9: Create queue ticket
        queue_ticket = QueueTicket(
            visit_id=new_visit.visit_id,
            queue_date=today,
            queue_status='WAITING',
            queue_position=new_position,
            estimated_wait_time=estimated_wait
        )
        db.add(queue_ticket)
        db.flush()
        
        # print(f"Created ticket #{queue_ticket.ticket_id}")
        
        # Commit all changes
        db.commit()
        
        return True, "Check-in successful", {
            "patient_id": patient.patient_id,
            "visit_id": new_visit.visit_id,
            "ticket_id": queue_ticket.ticket_id,
            "queue_position": new_position,
            "estimated_wait_time": estimated_wait
        }
        
    except Exception as e:
        db.rollback()
        # print(f"Error: {str(e)}")
        import traceback
        # print(traceback.format_exc())
        return False, f"Error during check-in: {str(e)}", {}
    
# Helper functions
def generate_otp(length=6):
    """Generate random OTP"""
    return ''.join(random.choices(string.digits, k=length))


def send_sms(phone_number: str, message: str):
    """
    TODO: Implement with Twilio
    For now, just print to console
    """
    # print(f"📱 SMS to {phone_number}: {message}")
    return True

