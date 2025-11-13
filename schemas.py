from pydantic import BaseModel, Field, validator
from typing import Optional,List
from datetime import datetime, date


class AppointmentStartRequest(BaseModel):
    """Request schema for starting an appointment"""
    ticket_id: int = Field(..., description="Queue ticket ID", example=3)
    doctor_id: Optional[int] = Field(None, description="Doctor ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": 3,
                "doctor_id": 5
            }
        }

class AppointmentStartResponse(BaseModel):
    """Response schema for appointment start"""
    success: bool
    message: str
    ticket_id: int
    visit_id: int
    patient_name: str
    queue_status: str
    started_at: str
    
    class Config:
        from_attributes = True

# OTP Verify Schemas
class OTPVerifyRequest(BaseModel):
    """Request schema for OTP verification"""
    phone_number: str = Field(..., description="Patient's phone number", example="+1-555-1011")
    otp_code: str = Field(..., description="6-digit OTP code", example="123456")
    department_id: Optional[int] = Field(None, description="Department ID")
    doctor_id: Optional[int] = Field(None, description="Doctor ID")
    check_in_method: str = Field(default="OTP", description="Check-in method")
    
    @validator('otp_code')
    def validate_otp_code(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('OTP code must be 6 digits')
        return v
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Invalid phone number')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "+1-555-1011",
                "otp_code": "123456",
                "department_id": 5,
                "doctor_id": 9,
                "check_in_method": "OTP"
            }
        }

class OTPVerifyResponse(BaseModel):
    """Response schema for OTP verification"""
    success: bool
    message: str
    patient_id: Optional[int] = None
    visit_id: Optional[int] = None
    ticket_id: Optional[int] = None
    queue_position: Optional[int] = None
    estimated_wait_time: Optional[int] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Check-in successful",
                "patient_id": 6,
                "visit_id": 16,
                "ticket_id": 16,
                "queue_position": 2,
                "estimated_wait_time": 30
            }
        }
        
# Request/Response Models
class QRCheckInRequest(BaseModel):
    phone_number: str
    qr_code_value: str
    first_name: str = None
    last_name: str = None
    date_of_birth: date = None
    
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "phone_number": "1234567890",
                "qr_code_value": "345678",
                "first_name": "abc",
                "last_name": "bcd",
                "date_of_birth": "2025-11-12"
                }
            }
        

class QRCheckInResponse(BaseModel):
    success: bool
    message: str
    patient_id: int
    visit_id: int
    ticket_id: int
    queue_position: int

class StatusUpdate(BaseModel):
    status: str
    
# Patient search response model
class PatientSearchResponse(BaseModel):
    patient_id: int
    first_name: str
    last_name: str
    phone_number: Optional[str]
    date_of_birth: Optional[date]
    gender: Optional[str]
    address: Optional[str]
    blood_group: Optional[str]
    rfid_tag: Optional[str]
    preferred_language: Optional[str]
    doctor_id: Optional[int]
    patient_type: Optional[str]
    is_active: bool
    emergency_contact_name: Optional[str]
    emergency_contact_number: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
        
# Request model
class OTPSendRequest(BaseModel):
    phone_number: str
 
# Response model
class OTPSendResponse(BaseModel):
    message: str
    otp_id: int
    otp_code: str
    expires_at: str
    

# Request/Response Models
class SMSCheckinRequest(BaseModel):
    phone_number: str
    message_body: str


class SMSCheckinResponse(BaseModel):
    success: bool
    message: str
    otp_required: bool = False
    visit_id: int = None
    queue_position: int = None
    
# Response Models
class QueuePatient(BaseModel):
    ticket_id: int
    patient_name: str
    queue_position: int
    queue_status: str
    estimated_wait_time: int
    check_in_time: str
    
    class Config:
        from_attributes = True


class ClinicianQueueResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    department_name: str
    total_patients: int
    queue_tickets: List[QueuePatient]
    
# Response Model
class AppointmentStatusResponse(BaseModel):
    visit_id: int
    patient_name: str
    doctor_name: str
    department_name: str
    visit_date: str
    visit_status: str
    check_in_datetime: Optional[str] = None
    queue_status: Optional[str] = None
    queue_position: Optional[int] = None
    estimated_wait_time: Optional[int] = None
    called_at: Optional[str] = None
    
    class Config:
        from_attributes = True
        
class CompleteAppointmentRequest(BaseModel):
    ticket_id: int


class CompleteAppointmentResponse(BaseModel):
    success: bool
    message: str
    ticket_id: int
    visit_id: int
    completed_at: datetime