# =============================================
# FILE: main.py (Updated)
# =============================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import apiRouter
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uvicorn
import os
import sys

app = FastAPI(
    title="Healthcare Queue Management API",
    description="API for managing patients",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(apiRouter.router)
# Include routers


#USE MAIN FOR TESTING NOT FOR PRODUCTION CODE, COMMENT BEFOR PUSHING
#USE THIS command TO RUN MAIN
# uvicorn main:app --reload
        
# if __name__ == "__main__":
    
#     # Get the directory of this file
#     current_dir = os.path.dirname(os.path.abspath(__file__))
    
#     # Add to Python path if needed
#     if current_dir not in sys.path:
#         sys.path.insert(0, current_dir)
    
#     # Run the server
#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=8000,
#         reload=True
#     )

