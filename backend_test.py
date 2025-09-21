import requests
import sys
import json
from datetime import datetime

class FarmtechAPITester:
    def __init__(self, base_url="https://kisan-tech-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.test_user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_phone = "+91 9876543210"

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        print(f"   Response: {response_data}")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_authentication_flow(self):
        """Test complete authentication flow"""
        print("\n" + "="*50)
        print("TESTING AUTHENTICATION FLOW")
        print("="*50)
        
        # Test OTP request
        success, response = self.run_test(
            "Request OTP",
            "POST",
            "auth/request-otp",
            200,
            data={"phone_number": self.test_phone}
        )
        
        if not success:
            return False
            
        mock_otp = response.get('mock_otp', '123456')
        print(f"   Mock OTP received: {mock_otp}")
        
        # Test OTP verification for new user
        success, response = self.run_test(
            "Verify OTP (New User)",
            "POST", 
            "auth/verify-otp",
            200,
            data={"phone_number": self.test_phone, "otp": mock_otp}
        )
        
        if not success or response.get('status') != 'new_user':
            print(f"❌ Expected new_user status, got: {response.get('status')}")
            return False
            
        # Test user registration
        registration_data = {
            "phone_number": self.test_phone,
            "name": "Test Farmer",
            "gender": "male", 
            "date_of_birth": "1990-01-01",
            "user_types": ["farmer", "worker"]
        }
        
        success, response = self.run_test(
            "Register User",
            "POST",
            "auth/register", 
            200,
            data=registration_data
        )
        
        if success:
            self.test_user = response
            print(f"   User registered with ID: {response.get('id')}")
            
        # Test OTP verification for existing user
        success, response = self.run_test(
            "Verify OTP (Existing User)",
            "POST",
            "auth/verify-otp", 
            200,
            data={"phone_number": self.test_phone, "otp": mock_otp}
        )
        
        if success and response.get('status') == 'existing_user':
            print("✅ Authentication flow completed successfully")
            return True
        else:
            print(f"❌ Expected existing_user status, got: {response.get('status')}")
            return False

    def test_weather_endpoints(self):
        """Test weather-related endpoints"""
        print("\n" + "="*50)
        print("TESTING WEATHER ENDPOINTS")
        print("="*50)
        
        # Test current weather
        success, response = self.run_test(
            "Get Current Weather",
            "POST",
            "weather/current",
            200,
            data={"latitude": 28.6139, "longitude": 77.2090}
        )
        
        if success:
            required_fields = ['temperature', 'humidity', 'description', 'wind_speed', 'farmer_recommendation']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                print(f"❌ Missing weather fields: {missing_fields}")
                return False
            else:
                print("✅ Weather data contains all required fields")
                return True
        return False

    def test_soil_analysis_endpoints(self):
        """Test soil analysis endpoints"""
        print("\n" + "="*50)
        print("TESTING SOIL ANALYSIS ENDPOINTS")
        print("="*50)
        
        if not self.test_user:
            print("❌ No test user available for soil analysis")
            return False
            
        # Test soil analysis with description only
        success, response = self.run_test(
            "Analyze Soil (Text Description)",
            "POST",
            "soil/analyze",
            200,
            data={
                "user_id": self.test_user['id'],
                "soil_description": "Dark brown soil with good moisture content, found in agricultural field in Punjab"
            }
        )
        
        if success:
            required_fields = ['analysis_id', 'result', 'timestamp']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                print(f"❌ Missing soil analysis fields: {missing_fields}")
                return False
            else:
                print("✅ Soil analysis completed successfully")
                print(f"   Analysis preview: {response['result'][:100]}...")
                return True
        return False

    def test_manpower_endpoints(self):
        """Test manpower marketplace endpoints"""
        print("\n" + "="*50)
        print("TESTING MANPOWER ENDPOINTS")
        print("="*50)
        
        if not self.test_user:
            print("❌ No test user available for manpower testing")
            return False
            
        # Test creating manpower listing
        listing_data = {
            "user_id": self.test_user['id'],
            "title": "Farm Worker Needed",
            "description": "Looking for experienced farm worker for wheat harvesting",
            "location": {"city": "Delhi", "state": "Delhi"},
            "payment": 500.0,
            "duration": "2 weeks"
        }
        
        success, response = self.run_test(
            "Create Manpower Listing",
            "POST",
            "manpower/create",
            200,
            data=listing_data
        )
        
        if not success:
            return False
            
        # Test getting manpower listings
        success, response = self.run_test(
            "Get Manpower Listings",
            "GET",
            "manpower/listings",
            200
        )
        
        if success and isinstance(response, list):
            print(f"✅ Retrieved {len(response)} manpower listings")
            return True
        return False

    def test_equipment_endpoints(self):
        """Test equipment rental endpoints"""
        print("\n" + "="*50)
        print("TESTING EQUIPMENT ENDPOINTS")
        print("="*50)
        
        if not self.test_user:
            print("❌ No test user available for equipment testing")
            return False
            
        # Test creating equipment listing
        equipment_data = {
            "user_id": self.test_user['id'],
            "equipment_name": "Tractor - Mahindra 575",
            "description": "Well-maintained tractor suitable for all farming operations",
            "daily_rate": 2000.0,
            "requires_operator": True,
            "location": {"city": "Delhi", "state": "Delhi"}
        }
        
        success, response = self.run_test(
            "Create Equipment Listing",
            "POST",
            "equipment/create",
            200,
            data=equipment_data
        )
        
        if not success:
            return False
            
        # Test getting equipment listings
        success, response = self.run_test(
            "Get Equipment Listings",
            "GET",
            "equipment/listings",
            200
        )
        
        if success and isinstance(response, list):
            print(f"✅ Retrieved {len(response)} equipment listings")
            return True
        return False

    def test_transport_endpoints(self):
        """Test transport booking endpoints"""
        print("\n" + "="*50)
        print("TESTING TRANSPORT ENDPOINTS")
        print("="*50)
        
        # Test transport price calculation
        success, response = self.run_test(
            "Calculate Transport Price",
            "POST",
            "transport/calculate-price",
            200,
            data={
                "pickup": {"address": "Delhi, India"},
                "delivery": {"address": "Mumbai, India"}
            }
        )
        
        if not success:
            return False
            
        # Verify pricing formula: ₹300 + (Distance × 15) + Other fees
        expected_fields = ['distance', 'base_price', 'distance_cost', 'other_fees', 'total_price']
        missing_fields = [field for field in expected_fields if field not in response]
        if missing_fields:
            print(f"❌ Missing pricing fields: {missing_fields}")
            return False
            
        # Verify formula calculation
        expected_total = response['base_price'] + response['distance_cost'] + response['other_fees']
        if abs(response['total_price'] - expected_total) > 0.01:
            print(f"❌ Price calculation error. Expected: {expected_total}, Got: {response['total_price']}")
            return False
            
        print(f"✅ Transport pricing formula verified: ₹{response['total_price']}")
        
        if not self.test_user:
            print("⚠️  Skipping transport booking (no test user)")
            return True
            
        # Test transport booking
        booking_data = {
            "farmer_id": self.test_user['id'],
            "pickup_location": {"address": "Delhi, India"},
            "delivery_location": {"address": "Mumbai, India"},
            "distance": response['distance'],
            "vehicle_type": "truck",
            "calculated_price": response['total_price']
        }
        
        success, response = self.run_test(
            "Book Transport",
            "POST",
            "transport/book",
            200,
            data=booking_data
        )
        
        return success

    def test_inventory_endpoints(self):
        """Test inventory management endpoints"""
        print("\n" + "="*50)
        print("TESTING INVENTORY ENDPOINTS")
        print("="*50)
        
        if not self.test_user:
            print("❌ No test user available for inventory testing")
            return False
            
        # Test adding inventory item
        inventory_data = {
            "user_id": self.test_user['id'],
            "item_name": "Wheat Seeds",
            "quantity": 100.0,
            "unit": "kg",
            "action": "sell",
            "price_per_unit": 25.0
        }
        
        success, response = self.run_test(
            "Add Inventory Item",
            "POST",
            "inventory/add",
            200,
            data=inventory_data
        )
        
        if not success:
            return False
            
        # Test getting user inventory
        success, response = self.run_test(
            "Get User Inventory",
            "GET",
            f"inventory/{self.test_user['id']}",
            200
        )
        
        if not success:
            return False
            
        # Test getting marketplace items
        success, response = self.run_test(
            "Get Marketplace Items",
            "GET",
            "marketplace/items",
            200
        )
        
        if success and isinstance(response, list):
            print(f"✅ Retrieved {len(response)} marketplace items")
            return True
        return False

    def test_schemes_and_insurance_endpoints(self):
        """Test government schemes and insurance endpoints"""
        print("\n" + "="*50)
        print("TESTING SCHEMES & INSURANCE ENDPOINTS")
        print("="*50)
        
        # Test government schemes
        success, response = self.run_test(
            "Get Government Schemes",
            "GET",
            "schemes",
            200
        )
        
        if not success or not isinstance(response, list):
            return False
            
        # Verify scheme structure
        if response:
            scheme = response[0]
            required_fields = ['id', 'name', 'description', 'eligibility', 'benefit', 'application_link']
            missing_fields = [field for field in required_fields if field not in scheme]
            if missing_fields:
                print(f"❌ Missing scheme fields: {missing_fields}")
                return False
                
        print(f"✅ Retrieved {len(response)} government schemes")
        
        # Test crop insurance
        success, response = self.run_test(
            "Get Crop Insurance",
            "GET",
            "insurance",
            200
        )
        
        if success and isinstance(response, list):
            print(f"✅ Retrieved {len(response)} insurance options")
            return True
        return False

    def test_user_profile_endpoint(self):
        """Test user profile endpoint"""
        print("\n" + "="*50)
        print("TESTING USER PROFILE ENDPOINT")
        print("="*50)
        
        if not self.test_user:
            print("❌ No test user available for profile testing")
            return False
            
        success, response = self.run_test(
            "Get User Profile",
            "GET",
            f"users/{self.test_user['id']}",
            200
        )
        
        if success:
            required_fields = ['id', 'phone_number', 'name', 'user_types']
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                print(f"❌ Missing profile fields: {missing_fields}")
                return False
            else:
                print("✅ User profile retrieved successfully")
                return True
        return False

def main():
    """Run all API tests"""
    print("🚀 Starting Farmtech API Testing")
    print("=" * 60)
    
    tester = FarmtechAPITester()
    
    # Run all test suites
    test_results = []
    
    test_results.append(("Authentication Flow", tester.test_authentication_flow()))
    test_results.append(("Weather Endpoints", tester.test_weather_endpoints()))
    test_results.append(("Soil Analysis", tester.test_soil_analysis_endpoints()))
    test_results.append(("Manpower Marketplace", tester.test_manpower_endpoints()))
    test_results.append(("Equipment Rental", tester.test_equipment_endpoints()))
    test_results.append(("Transport Booking", tester.test_transport_endpoints()))
    test_results.append(("Inventory Management", tester.test_inventory_endpoints()))
    test_results.append(("Schemes & Insurance", tester.test_schemes_and_insurance_endpoints()))
    test_results.append(("User Profile", tester.test_user_profile_endpoint()))
    
    # Print final results
    print("\n" + "="*60)
    print("📊 FINAL TEST RESULTS")
    print("="*60)
    
    passed_suites = 0
    for suite_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{suite_name:<25} {status}")
        if result:
            passed_suites += 1
    
    print(f"\n📈 Overall Results:")
    print(f"   Test Suites: {passed_suites}/{len(test_results)} passed")
    print(f"   Individual Tests: {tester.tests_passed}/{tester.tests_run} passed")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if passed_suites == len(test_results):
        print("\n🎉 All API tests passed! Backend is ready for frontend integration.")
        return 0
    else:
        print(f"\n⚠️  {len(test_results) - passed_suites} test suite(s) failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())