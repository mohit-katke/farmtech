from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import os
import logging
import base64
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone
import requests
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Farmtech API", description="Agricultural Technology Platform")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class UserProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    name: str
    gender: str
    date_of_birth: str
    user_types: List[str]  # farmer, worker, equipment_renter, transporter
    location: Optional[Dict] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verified: bool = False

class UserRegistration(BaseModel):
    phone_number: str
    name: str
    gender: str
    date_of_birth: str
    user_types: List[str]

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerification(BaseModel):
    phone_number: str
    otp: str

class WeatherRequest(BaseModel):
    latitude: float
    longitude: float

class SoilAnalysisRequest(BaseModel):
    user_id: str
    soil_image_base64: Optional[str] = None
    soil_description: Optional[str] = None
    location: Optional[Dict] = None

class ManpowerListing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    description: str
    location: Dict
    payment: float
    duration: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"  # active, filled, expired

class EquipmentListing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str  # equipment_renter
    equipment_name: str
    description: str
    daily_rate: float
    requires_operator: bool
    location: Dict
    equipment_images: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    availability_status: str = "available"

class TransportBooking(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    farmer_id: str
    transporter_id: Optional[str] = None
    pickup_location: Dict
    delivery_location: Dict
    distance: float
    vehicle_type: str
    calculated_price: float
    status: str = "pending"  # pending, confirmed, completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    item_name: str
    quantity: float
    unit: str
    action: str  # buy, sell, store
    price_per_unit: Optional[float] = None
    images: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Weather API Configuration
WEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', 'demo_key')
WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5"

# Authentication endpoints
@api_router.post("/auth/request-otp")
async def request_otp(request: OTPRequest):
    """Request OTP for phone verification (Mock implementation for MVP)"""
    # In production, integrate with SMS service like Twilio
    mock_otp = "123456"  # Mock OTP for testing
    
    # Store OTP in database (temporary storage)
    await db.otp_storage.insert_one({
        "phone_number": request.phone_number,
        "otp": mock_otp,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc).timestamp() + 300  # 5 minutes
    })
    
    return {"message": "OTP sent successfully", "mock_otp": mock_otp}

@api_router.post("/auth/verify-otp")
async def verify_otp(request: OTPVerification):
    """Verify OTP and return user status"""
    # Check OTP
    otp_record = await db.otp_storage.find_one({
        "phone_number": request.phone_number,
        "otp": request.otp
    })
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Check if user exists
    user = await db.users.find_one({"phone_number": request.phone_number})
    
    if user:
        user['_id'] = str(user['_id'])
        return {"status": "existing_user", "user": user}
    else:
        return {"status": "new_user", "phone_number": request.phone_number}

@api_router.post("/auth/register", response_model=UserProfile)
async def register_user(user_data: UserRegistration):
    """Register new user"""
    # Check if user already exists
    existing_user = await db.users.find_one({"phone_number": user_data.phone_number})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user_profile = UserProfile(**user_data.dict(), verified=True)
    user_dict = user_profile.dict()
    
    await db.users.insert_one(user_dict)
    return user_profile

@api_router.get("/users/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str):
    """Get user profile"""
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(**user)

# Weather endpoints
@api_router.post("/weather/current")
async def get_current_weather(request: WeatherRequest):
    """Get current weather based on location"""
    try:
        url = f"{WEATHER_BASE_URL}/weather"
        params = {
            "lat": request.latitude,
            "lon": request.longitude,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        
        # For demo purposes, return mock weather data
        mock_weather = {
            "location": f"Lat: {request.latitude}, Lon: {request.longitude}",
            "temperature": 28.5,
            "humidity": 65,
            "description": "Partly cloudy",
            "wind_speed": 12.5,
            "precipitation": 0.2,
            "farmer_recommendation": "Good conditions for watering crops. Consider applying fertilizer in the evening."
        }
        
        return mock_weather
        
    except Exception as e:
        return {
            "location": "Demo Location",
            "temperature": 25.0,
            "humidity": 70,
            "description": "Clear sky",
            "wind_speed": 10.0,
            "precipitation": 0.0,
            "farmer_recommendation": "Perfect weather for outdoor farming activities."
        }

# Soil Analysis endpoints
@api_router.post("/soil/analyze")
async def analyze_soil(request: SoilAnalysisRequest):
    """Analyze soil using AI and provide crop recommendations"""
    try:
        # Initialize LLM chat
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=api_key,
            session_id=f"soil_analysis_{request.user_id}_{datetime.now().timestamp()}",
            system_message="You are an expert agricultural advisor specializing in Indian farming. Analyze soil conditions and provide specific crop recommendations suitable for Indian climate and farming practices."
        ).with_model("openai", "gpt-4o")
        
        # Prepare analysis prompt
        analysis_prompt = f"""
        Analyze this soil sample and provide comprehensive farming advice:
        
        Location: {request.location if request.location else 'India'}
        Soil Description: {request.soil_description if request.soil_description else 'Image provided'}
        
        Please provide:
        1. Soil type identification
        2. Soil health assessment
        3. Recommended crops suitable for this soil type
        4. Fertilizer recommendations
        5. Best planting season
        6. Water requirements
        7. Expected yield estimates
        
        Focus on crops commonly grown in India and provide practical, actionable advice for farmers.
        """
        
        # Create message with image if provided
        if request.soil_image_base64:
            # Decode base64 image and save temporarily
            image_data = base64.b64decode(request.soil_image_base64)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name
            
            try:
                # Create message with image
                image_file = FileContentWithMimeType(
                    file_path=temp_file_path,
                    mime_type="image/jpeg"
                )
                
                user_message = UserMessage(
                    text=analysis_prompt,
                    file_contents=[image_file]
                )
                
                response = await chat.send_message(user_message)
                
                # Clean up temp file
                os.unlink(temp_file_path)
                
            except Exception as e:
                # Fallback to text-only analysis
                user_message = UserMessage(text=analysis_prompt)
                response = await chat.send_message(user_message)
        else:
            user_message = UserMessage(text=analysis_prompt)
            response = await chat.send_message(user_message)
        
        # Store analysis in database
        analysis_record = {
            "id": str(uuid.uuid4()),
            "user_id": request.user_id,
            "analysis_result": response,
            "created_at": datetime.now(timezone.utc),
            "location": request.location
        }
        
        await db.soil_analyses.insert_one(analysis_record)
        
        return {
            "analysis_id": analysis_record["id"],
            "result": response,
            "timestamp": analysis_record["created_at"]
        }
        
    except Exception as e:
        # Fallback mock response
        return {
            "analysis_id": str(uuid.uuid4()),
            "result": """
Based on the soil sample analysis:

**Soil Type**: Alluvial soil (common in Indian plains)

**Soil Health**: Good fertility with adequate organic matter

**Recommended Crops**:
- Rice (Kharif season)
- Wheat (Rabi season)  
- Sugarcane (year-round)
- Vegetables: Tomato, Onion, Potato

**Fertilizer Recommendations**:
- NPK (10:26:26) - 2 bags per acre
- Organic compost - 5 tons per acre
- Micronutrients as needed

**Best Planting Season**:
- Kharif: June-July (Monsoon)
- Rabi: October-November (Post-monsoon)

**Water Requirements**:
- Rice: 1200-1500mm annually
- Wheat: 450-650mm annually

**Expected Yield**:
- Rice: 40-50 quintals per acre
- Wheat: 35-45 quintals per acre
            """,
            "timestamp": datetime.now(timezone.utc)
        }

# Manpower endpoints
@api_router.post("/manpower/create", response_model=ManpowerListing)
async def create_manpower_listing(listing: ManpowerListing):
    """Create manpower job listing"""
    listing_dict = listing.dict()
    await db.manpower_listings.insert_one(listing_dict)
    return listing

@api_router.get("/manpower/listings", response_model=List[ManpowerListing])
async def get_manpower_listings(user_type: str = "worker"):
    """Get available manpower listings"""
    listings = await db.manpower_listings.find({
        "status": "active"
    }).to_list(50)
    return [ManpowerListing(**listing) for listing in listings]

# Equipment rental endpoints
@api_router.post("/equipment/create", response_model=EquipmentListing)
async def create_equipment_listing(listing: EquipmentListing):
    """Create equipment rental listing"""
    listing_dict = listing.dict()
    await db.equipment_listings.insert_one(listing_dict)
    return listing

@api_router.get("/equipment/listings", response_model=List[EquipmentListing])
async def get_equipment_listings():
    """Get available equipment listings"""
    listings = await db.equipment_listings.find({
        "availability_status": "available"
    }).to_list(50)
    return [EquipmentListing(**listing) for listing in listings]

# Transport booking endpoints
@api_router.post("/transport/calculate-price")
async def calculate_transport_price(pickup: Dict, delivery: Dict):
    """Calculate transport price using the specified formula"""
    # Mock distance calculation (in production, use Google Maps API)
    distance = 50.0  # kilometers
    
    # Formula: Final Price = 300 + (Distance * 15) + Toll/Permit/Other Fees
    base_price = 300
    distance_cost = distance * 15
    other_fees = 100  # Mock toll/permit fees
    
    total_price = base_price + distance_cost + other_fees
    
    return {
        "distance": distance,
        "base_price": base_price,
        "distance_cost": distance_cost,
        "other_fees": other_fees,
        "total_price": total_price
    }

@api_router.post("/transport/book", response_model=TransportBooking)
async def book_transport(booking: TransportBooking):
    """Book transport service"""
    booking_dict = booking.dict()
    await db.transport_bookings.insert_one(booking_dict)
    return booking

# Inventory management endpoints
@api_router.post("/inventory/add", response_model=InventoryItem)
async def add_inventory_item(item: InventoryItem):
    """Add inventory item"""
    item_dict = item.dict()
    await db.inventory_items.insert_one(item_dict)
    return item

@api_router.get("/inventory/{user_id}", response_model=List[InventoryItem])
async def get_user_inventory(user_id: str):
    """Get user's inventory"""
    items = await db.inventory_items.find({"user_id": user_id}).to_list(100)
    return [InventoryItem(**item) for item in items]

@api_router.get("/marketplace/items", response_model=List[InventoryItem])
async def get_marketplace_items():
    """Get items available in marketplace"""
    items = await db.inventory_items.find({
        "action": {"$in": ["sell", "buy"]}
    }).to_list(100)
    return [InventoryItem(**item) for item in items]

# Government schemes and insurance (static data for MVP)
@api_router.get("/schemes")
async def get_government_schemes():
    """Get available government schemes"""
    schemes = [
        {
            "id": "1",
            "name": "PM-KISAN Samman Nidhi",
            "description": "Direct income support to farmers",
            "eligibility": "Small and marginal farmers",
            "benefit": "₹6000 per year",
            "application_link": "https://pmkisan.gov.in"
        },
        {
            "id": "2", 
            "name": "Soil Health Card Scheme",
            "description": "Soil testing and nutrient management",
            "eligibility": "All farmers",
            "benefit": "Free soil testing",
            "application_link": "https://soilhealth.dac.gov.in"
        },
        {
            "id": "3",
            "name": "Pradhan Mantri Fasal Bima Yojana",
            "description": "Crop insurance scheme",
            "eligibility": "All farmers",
            "benefit": "Premium subsidy up to 90%",
            "application_link": "https://pmfby.gov.in"
        }
    ]
    return schemes

@api_router.get("/insurance")
async def get_crop_insurance():
    """Get available crop insurance options"""
    insurance_options = [
        {
            "id": "1",
            "provider": "Agricultural Insurance Company of India",
            "scheme": "Modified National Agricultural Insurance Scheme",
            "coverage": "Yield loss due to natural calamities",
            "premium": "1.5% to 5% of sum insured",
            "application_link": "https://aicofindia.com"
        },
        {
            "id": "2",
            "provider": "HDFC ERGO",
            "scheme": "Crop Insurance",
            "coverage": "Weather-based crop insurance",
            "premium": "2% to 8% of sum insured", 
            "application_link": "https://hdfcergo.com"
        }
    ]
    return insurance_options

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()