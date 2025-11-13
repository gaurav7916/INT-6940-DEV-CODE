from sqlalchemy import Boolean, Column, Integer, String, Date, Text, DateTime,ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class QueueTicket(Base):
    __tablename__ = "queue_tickets"
    
    ticket_id = Column(Integer, primary_key=True, autoincrement=True)
    visit_id = Column(Integer, ForeignKey("visits.visit_id"), unique=True)
    queue_date = Column(Date)
    queue_status = Column(String, default="waiting")
    queue_position = Column(Integer)
    estimated_wait_time = Column(Integer)
    called_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(Integer)
    
    visit = relationship("Visit", back_populates="queue_ticket")


class Visit(Base):
    __tablename__ = "visits"
    
    visit_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"))
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    doctor_id = Column(Integer, ForeignKey("doctors.doctor_id"))
    visit_date = Column(Date)
    check_in_datetime = Column(DateTime)
    check_in_method = Column(String)
    visit_status = Column(String, default="scheduled")
    completed_datetime = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    patient = relationship("Patient", back_populates="visits")
    department = relationship("Department", back_populates="visits")
    doctor = relationship("Doctor", back_populates="visits")
    queue_ticket = relationship("QueueTicket", back_populates="visit", uselist=False)

    
#OTP Verification table
class OTPVerification(Base):
    __tablename__ = "otp_verifications"
    
    otp_id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False, index=True)
    otp_code = Column(String(10), nullable=False)
    is_verified = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    patient_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Patient table
class Patient(Base):
    __tablename__ = "patients"
    patient_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), unique=True)
    date_of_birth = Column(Date)
    gender = Column(String(20))
    address = Column(Text)
    blood_group = Column(String(10))
    rfid_tag = Column(String(50))
    preferred_language = Column(String(50))
    doctor_id = Column(Integer)
    patient_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    emergency_contact_name = Column(String(100))
    emergency_contact_number = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(Integer)
    
    # ADD THIS LINE:
    visits = relationship("Visit", back_populates="patient")
    
class Department(Base):
    __tablename__ = "departments"
    
    department_id = Column(Integer, primary_key=True, autoincrement=True)
    department_code = Column(String, unique=True)
    department_name = Column(String)
    description = Column(String)
    average_service_time = Column(Integer)
    max_queue_size = Column(Integer)
    business_hours_number = Column(Integer)
    buffer_time_minutes = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    doctors = relationship("Doctor", back_populates="department")
    visits = relationship("Visit", back_populates="department")
    
class Doctor(Base):
    __tablename__ = "doctors"
    
    doctor_id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String)
    last_name = Column(String)
    specialization = Column(String)
    phone_number = Column(String)
    email = Column(String)
    department_id = Column(Integer, ForeignKey("departments.department_id"))
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    department = relationship("Department", back_populates="doctors")
    visits = relationship("Visit", back_populates="doctor")
    
class CheckInLog(Base):
    __tablename__ = "check_in_logs"
    
    check_in_log_id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.visit_id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"), nullable=False)
    check_in_method = Column(String(20), nullable=False)
    qr_code_value = Column(String(100))
    check_in_datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    success = Column(Boolean, default=True)
    error_message = Column(String(500))