from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session  
from database import get_db,engine
from schemas import *
import crud
from typing import List, Optional, Annotated
import random
from fastapi import Query
import models
from datetime import datetime, date, timedelta

models.Base.metadata.create_all(bind=engine)

router = APIRouter(
    prefix="/api",
    tags=["apiRouter"]
)

db_dependency = Annotated[Session, Depends(get_db)]

@router.post("/appointments/start", response_model=AppointmentStartResponse, status_code=status.HTTP_200_OK)
async def start_appointment(
    request: AppointmentStartRequest,
    db: db_dependency, # type: ignore
):
    """
    Start an appointment (change status from WAITING/CALLED to IN_PROGRESS)
    
    - **ticket_id**: Queue ticket ID to start
    - **doctor_id**: Optional doctor ID starting the appointment
    """
    success, message, data = crud.start_appointment(db, request)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return AppointmentStartResponse(
        success=success,
        message=message,
        ticket_id=data.get("ticket_id"),
        visit_id=data.get("visit_id"),
        patient_name=data.get("patient_name"),
        queue_status=data.get("queue_status"),
        started_at=data.get("started_at").isoformat()
    )

@router.post("/otp/verify", response_model=OTPVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_otp(
    request: OTPVerifyRequest,
    db: db_dependency, # type: ignore
):
    """
    Verify OTP and complete patient check-in
    
    - **phone_number**: Patient's registered phone number
    - **otp_code**: 4-digit OTP code sent to patient
    - **department_id**: Optional department ID for check-in
    - **doctor_id**: Optional doctor ID for appointment
    - **check_in_method**: Method used for check-in (default: OTP)
    
    Returns:
    - Patient ID, Visit ID, Ticket ID, Queue position, and estimated wait time
    """
    success, message, data = crud.verify_otp_and_checkin(db, request)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    return OTPVerifyResponse(
        success=success,
        message=message,
        patient_id=data.get("patient_id"),
        visit_id=data.get("visit_id"),
        ticket_id=data.get("ticket_id"),
        queue_position=data.get("queue_position"),
        estimated_wait_time=data.get("estimated_wait_time")
    )
    

@router.post("/checkin/qr", response_model=QRCheckInResponse)
def qr_checkin(request: QRCheckInRequest, db: db_dependency,): # type: ignore
    """QR Code Check-in endpoint"""
    
    # Check if patient exists
    patient = db.query(models.Patient).filter(
        models.Patient.phone_number == request.phone_number,
        models.Patient.is_active == True
    ).first()
    
    # If new patient, create record
    if not patient:
        if not request.first_name or not request.last_name or not request.date_of_birth:
            raise HTTPException(
                status_code=400,
                detail="For new patients: first_name, last_name, and date_of_birth are required"
            )
        
        patient = models.Patient(
            first_name=request.first_name,
            last_name=request.last_name,
            phone_number=request.phone_number,
            date_of_birth=request.date_of_birth
        )
        db.add(patient)
        db.flush()
    
    # Create visit
    visit = models.Visit(
        patient_id=patient.patient_id,
        visit_date=date.today(),
        check_in_datetime=datetime.utcnow(),
        check_in_method="QR_CODE",
        visit_status="ACTIVE"
    )
    db.add(visit)
    db.flush()
    
    # Calculate queue position
    today = date.today()
    max_position = db.query(models.QueueTicket).filter(models.QueueTicket.queue_date == today).count()
    queue_position = max_position + 1
    
    # Create queue ticket
    queue_ticket = models.QueueTicket(
        visit_id=visit.visit_id,
        queue_date=today,
        queue_status="WAITING",
        queue_position=queue_position
    )
    db.add(queue_ticket)
    db.commit()
    
    return QRCheckInResponse(
        success=True,
        message="Check-in successful",
        patient_id=patient.patient_id,
        visit_id=visit.visit_id,
        ticket_id=queue_ticket.ticket_id,
        queue_position=queue_position
    )

@router.patch("/appointment/{ticket_id}/status")
def update_appointment_status(ticket_id: int, request: StatusUpdate, db: db_dependency ):# type: ignore
    """Update appointment/queue ticket status"""
    
    # Valid statuses
    valid_statuses = ["WAITING", "CALLED", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # Find ticket
    ticket = db.query(models.QueueTicket).filter(models.QueueTicket.ticket_id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Update status with timestamps
    old_status = ticket.queue_status
    ticket.queue_status = request.status
    
    if request.status == "CALLED":
        ticket.called_at = datetime.utcnow()
    elif request.status == "IN_PROGRESS":
        ticket.started_at = datetime.utcnow()
    elif request.status in ["COMPLETED", "CANCELLED"]:
        ticket.completed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Status updated to {request.status}",
        "ticket_id": ticket_id,
        "old_status": old_status,
        "new_status": request.status
    }


@router.get("/patients/search", response_model=List[PatientSearchResponse])
def search_patients(
    db: db_dependency,  # type: ignore
    first_name: Optional[str] = Query(None, description="Search by first name"),
    last_name: Optional[str] = Query(None, description="Search by last name"),
    phone_number: Optional[str] = Query(None, description="Search by phone number"),
    patient_id: Optional[int] = Query(None, description="Search by patient ID"),
    blood_group: Optional[str] = Query(None, description="Filter by blood group"),
    patient_type: Optional[str] = Query(None, description="Filter by patient type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results")
):
    """
    Search patients by multiple criteria.
    All search parameters are optional and can be combined.
    Returns a list of matching patients.
    """
    
    # Start with base query, excluding soft-deleted records
    query = db.query(models.Patient).filter(models.Patient.deleted_at.is_(None))
    
    # Apply filters based on provided parameters
    if patient_id is not None:
        query = query.filter(models.Patient.patient_id == patient_id)
    
    if first_name:
        query = query.filter(models.Patient.first_name.ilike(f"%{first_name}%"))
    
    if last_name:
        query = query.filter(models.Patient.last_name.ilike(f"%{last_name}%"))
    
    if phone_number:
        query = query.filter(models.Patient.phone_number.ilike(f"%{phone_number}%"))
    
    if blood_group:
        query = query.filter(models.Patient.blood_group == blood_group)
    
    if patient_type:
        query = query.filter(models.Patient.patient_type == patient_type)
    
    if is_active is not None:
        query = query.filter(models.Patient.is_active == is_active)
    
    # Execute query with limit
    patients = query.limit(limit).all()
    
    # If no filters provided, return empty list or raise error
    if all(param is None for param in [patient_id, first_name, last_name, phone_number, blood_group, patient_type, is_active]):
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter must be provided"
        )
    
    return patients
 
 
@router.post("/otp/send", response_model=OTPSendResponse)
def send_otp(request: OTPSendRequest, db: db_dependency): # type: ignore
    # Check for existing active OTP
    existing_otp = db.query(models.OTPVerification).filter(
        models.OTPVerification.phone_number == request.phone_number,
        models.OTPVerification.is_expired == False,
        models.OTPVerification.is_verified == False
    ).first()
    
    # If exists and not expired, check retry count
    if existing_otp:
        if existing_otp.retry_count >= existing_otp.max_attempts:
            raise HTTPException(
                status_code=429,
                detail="Maximum OTP request attempts reached. Please try again later."
            )
        
        # Increment retry count
        existing_otp.retry_count += 1
        existing_otp.updated_at = datetime.now()
        db.commit()
        db.refresh(existing_otp)
        
        return OTPSendResponse(
            message="OTP resent successfully",
            otp_id=existing_otp.otp_id,
            otp_code=existing_otp.otp_code,
            expires_at=existing_otp.expires_at.isoformat()
        )
    
    # Generate 4-digit OTP
    otp_code = str(random.randint(1000, 9999))
    # Set expiration (5 minutes from now)
    expires_at = datetime.now() + timedelta(minutes=5)
    
    # Create new OTP record
    new_otp = models.OTPVerification(
        phone_number=request.phone_number,
        otp_code=otp_code,
        is_verified=False,
        is_expired=False,
        created_at=datetime.now(),
        expires_at=expires_at,
        retry_count=0,
        max_attempts=3,
        updated_at=datetime.now()
    )
    
    db.add(new_otp)
    db.commit()
    db.refresh(new_otp)
    
    # TODO: Send OTP via SMS service (Twilio, etc.)
    print(f"OTP for {request.phone_number}: {otp_code}")
    
    return OTPSendResponse(
        message="OTP sent successfully",
        otp_id=new_otp.otp_id,
        otp_code=new_otp.otp_code,
        expires_at=new_otp.expires_at.isoformat()
    )
    
@router.post("/checkin/sms", response_model=SMSCheckinResponse)
async def sms_checkin(request: SMSCheckinRequest, db: db_dependency): # type: ignore
    """
    Handle SMS check-in when patient texts 'JOIN'
    
    This endpoint:
    1. Validates the patient exists
    2. Checks for today's appointment
    3. Generates OTP and saves to database
    4. Sends OTP via SMS
    5. Returns success response
    """
    
    # Validate message is "JOIN"
    if request.message_body.strip().upper() != "JOIN":
        return SMSCheckinResponse(
            success=False,
            message="Invalid message. Please text 'JOIN' to check in."
        )
    
    # Step 1: Find patient by phone number
    patient = db.query(models.Patient).filter(
        models.Patient.phone_number == request.phone_number,
        models.Patient.is_active == True
    ).first()
    
    if not patient:
        return SMSCheckinResponse(
            success=False,
            message="Patient not found. Please register first."
        )
    
    # Step 2: Check for today's appointment
    today = date.today()
    visit = db.query(models.Visit).filter(
        models.Visit.patient_id == patient.patient_id,
        models.Visit.visit_date == today,
        models.Visit.visit_status == "scheduled"
    ).first()
    
    if not visit:
        return SMSCheckinResponse(
            success=False,
            message="No appointment scheduled for today."
        )
    
    # Step 3: Check if already checked in
    if visit.check_in_datetime is not None:
        return SMSCheckinResponse(
            success=False,
            message="You have already checked in."
        )
    
    # Step 4: Generate and send OTP
    otp_code = crud.generate_otp()
    expires_at = datetime.now() + timedelta(minutes=10)
    
    # Save OTP to database
    otp_record = models.OTPVerification(
        phone_number=request.phone_number,
        otp_code=otp_code,
        patient_id=patient.patient_id,
        expires_at=expires_at,
        is_verified=False
    )
    db.add(otp_record)
    db.commit()
    
    # Send OTP via SMS
    sms_message = f"Your check-in OTP is: {otp_code}. Valid for 10 minutes."
    crud.send_sms(request.phone_number, sms_message)
    
    return SMSCheckinResponse(
        success=True,
        message="OTP sent to your phone. Please reply with the code.",
        otp_required=True,
        visit_id=visit.visit_id
    )

@router.get("/queue/clinician/{clinician_id}", response_model=ClinicianQueueResponse)
async def get_clinician_queue(
    clinician_id: int, db: db_dependency, queue_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format")): # type: ignore
    """
    Get the queue for a specific clinician/doctor
    
    Returns all patients waiting in the doctor's queue with their positions
    """
    
    # Step 1: Get doctor info
    doctor = db.query(models.Doctor).filter(
        models.Doctor.doctor_id == clinician_id,
        models.Doctor.is_active == True
    ).first()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Step 2: Get department info
    department = db.query(models.Department).filter(
        models.Department.department_id == doctor.department_id
    ).first()
    
    # Step 3: Parse date or use today
    if queue_date:
        try:
            target_date = date.fromisoformat(queue_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    else:
        target_date = date.today()
    
    # Step 4: Get all queue tickets for this doctor today
    queue_tickets = db.query(models.QueueTicket).join(models.Visit).filter(
        models.Visit.doctor_id == clinician_id,
        models.QueueTicket.queue_date == target_date,
        models.QueueTicket.queue_status.in_(["waiting", "called", "in_progress"])
    ).order_by(models.QueueTicket.queue_position).all()
    
    # Step 5: Build response with patient details
    patients_list = []
    for ticket in queue_tickets:
        # Get visit and patient info
        visit = db.query(models.Visit).filter(models.Visit.visit_id == ticket.visit_id).first()
        patient = db.query(models.Patient).filter(
            models.Patient.patient_id == visit.patient_id
        ).first()
        
        patients_list.append(QueuePatient(
            ticket_id=ticket.ticket_id,
            patient_name=f"{patient.first_name} {patient.last_name}",
            queue_position=ticket.queue_position,
            queue_status=ticket.queue_status,
            estimated_wait_time=ticket.estimated_wait_time,
            check_in_time=visit.check_in_datetime.isoformat() if visit.check_in_datetime else ""
        ))
    
    return ClinicianQueueResponse(
        doctor_id=doctor.doctor_id,
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
        department_name=department.department_name if department else "Unknown",
        total_patients=len(patients_list),
        queue_tickets=patients_list
    )


@router.get("/appointment/status/{appointment_id}", response_model=AppointmentStatusResponse)
async def get_appointment_status(
    appointment_id: int,
    db: db_dependency # type: ignore
):
    """
    Get the current status of an appointment (visit)
    
    Returns complete appointment info including queue status if checked in
    """
    
    # Step 1: Get the visit/appointment
    visit = db.query(models.Visit).filter(
        models.Visit.visit_id == appointment_id
    ).first()
    
    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    # Step 2: Get patient details
    patient = db.query(models.Patient).filter(
        models.Patient.patient_id == visit.patient_id
    ).first()
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    # Step 3: Get doctor details
    doctor = db.query(models.Doctor).filter(
        models.Doctor.doctor_id == visit.doctor_id
    ).first()
    
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found"
        )
    
    # Step 4: Get department details
    department = db.query(models.Department).filter(
        models.Department.department_id == visit.department_id
    ).first()
    
    # Step 5: Get queue ticket if exists
    queue_ticket = db.query(models.QueueTicket).filter(
        models.QueueTicket.visit_id == visit.visit_id
    ).first()
    
    # Step 6: Build response
    return AppointmentStatusResponse(
        visit_id=visit.visit_id,
        patient_name=f"{patient.first_name} {patient.last_name}",
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
        department_name=department.department_name if department else "Unknown",
        visit_date=visit.visit_date.isoformat(),
        visit_status=visit.visit_status,
        check_in_datetime=visit.check_in_datetime.isoformat() if visit.check_in_datetime else None,
        queue_status=queue_ticket.queue_status if queue_ticket else None,
        queue_position=queue_ticket.queue_position if queue_ticket else None,
        estimated_wait_time=queue_ticket.estimated_wait_time if queue_ticket else None,
        called_at=queue_ticket.called_at.isoformat() if queue_ticket and queue_ticket.called_at else None
    )
    
# Endpoint 3: Complete Appointment
@router.post("/appointment/complete", response_model=CompleteAppointmentResponse)
def complete_appointment(request: CompleteAppointmentRequest, db: Session = Depends(get_db)):
    """Complete an appointment"""
    queue_ticket = db.query(models.QueueTicket).filter(
        models.QueueTicket.ticket_id == request.ticket_id
    ).first()
    
    if not queue_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    queue_ticket.queue_status = "COMPLETED"
    queue_ticket.completed_at = datetime.utcnow()
    queue_ticket.updated_at = datetime.utcnow()
    
    visit = db.query(models.Visit).filter(models.Visit.visit_id == queue_ticket.visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    visit.visit_status = "COMPLETED"
    visit.completed_datetime = datetime.utcnow()
    visit.updated_at = datetime.utcnow()
    
    db.commit()
    
    return CompleteAppointmentResponse(
        success=True,
        message="Appointment completed successfully",
        ticket_id=queue_ticket.ticket_id,
        visit_id=visit.visit_id,
        completed_at=queue_ticket.completed_at
    )
