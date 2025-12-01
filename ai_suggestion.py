# AI Suggestions Service for AgriLink
# Single route for all AI message suggestions with role differentiation

from flask import Blueprint, request, jsonify
import re
import json
import time
from datetime import datetime
from openai import OpenAI

# Create blueprint for AI suggestions
ai_suggestions_bp = Blueprint('ai_suggestions', __name__)

# Initialize OpenAI client (will be set from main app)
client = None

def init_openai(api_key):
    """Initialize OpenAI client with API key"""
    global client
    client = OpenAI(api_key=api_key)

def generate_partial_summary(conversation_text, listing_name):
    """Generate partial summary from conversation when user requests it"""
    summary_lines = []
    
    # Extract buyer name (look for names in conversation)
    import re
    name_patterns = [
        r'my name is (\w+)',
        r'i am (\w+)',
        r'(\w+) here',
        r'i\'m (\w+)'
    ]
    
    buyer_name = "Not specified"
    for pattern in name_patterns:
        match = re.search(pattern, conversation_text, re.IGNORECASE)
        if match:
            buyer_name = match.group(1)
            break
    
    # Extract price (look for currency symbols or price keywords)
    price_patterns = [
        r'[₱$]\s*(\d+)',
        r'price[:\s]*(\d+)',
        r'cost[:\s]*(\d+)',
        r'(\d+)\s*(pesos|php)'
    ]
    
    price = "Not specified"
    for pattern in price_patterns:
        match = re.search(pattern, conversation_text, re.IGNORECASE)
        if match:
            price = match.group(1)
            break
    
    # Extract quantity
    quantity_patterns = [
        r'(\d+)\s*(kg|kilo|pcs|pieces|units)',
        r'quantity[:\s]*(\d+)',
        r'(\d+)\s*(pieces|units)'
    ]
    
    quantity = "Not specified"
    for pattern in quantity_patterns:
        match = re.search(pattern, conversation_text, re.IGNORECASE)
        if match:
            quantity = f"{match.group(1)} {match.group(2)}"
            break
    
    # Extract payment method
    payment_method = "Not specified"
    if 'cash on delivery' in conversation_text.lower() or 'cash upon delivery' in conversation_text.lower():
        payment_method = "cash upon delivery"
    elif 'cash on meetup' in conversation_text.lower():
        payment_method = "cash on meetup"
    elif 'cash on pickup' in conversation_text.lower():
        payment_method = "cash on pickup"
    
    # Extract location
    location = "Not specified"
    location_patterns = [
        r'location[:\s]*([^\n]+)',
        r'at ([^\n,]+)',
        r'meet at ([^\n,]+)'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, conversation_text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            break
    
    # Build summary
    summary_lines.append(f"buyer name: {buyer_name}")
    summary_lines.append(f"listing name: {listing_name}")
    summary_lines.append(f"listing price: {price}")
    summary_lines.append(f"listing quantity: {quantity}")
    summary_lines.append(f"mode of payment: {payment_method}")
    summary_lines.append(f"location: {location}")
    
    return '\n'.join(summary_lines)

def parse_transaction_summary(summary_text):
    """Parse AI-generated text summary into JSON object for frontend"""
    if not summary_text:
        return None
    
    summary_dict = {}
    lines = summary_text.strip().split('\n')
    
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            # Map backend keys to frontend field names
            if key == 'buyer name':
                summary_dict['name'] = value
            elif key == 'listing name':
                summary_dict['listingName'] = value
            elif key == 'listing price':
                summary_dict['price'] = value
            elif key == 'listing quantity':
                summary_dict['quantity'] = value
            elif key == 'mode of payment':
                summary_dict['paymentMethod'] = value
            elif key == 'location':
                summary_dict['location'] = value
    
    return summary_dict if summary_dict else None

def validate_suggestions(suggestions, detected_language='english'):
    """Filter out suggestions containing numbers, currency, or quantity words"""
    print("🔍 VALIDATING SUGGESTIONS FOR NUMBERS/CURRENCY")
    print(f"🔍 DEBUG: Detected language: {detected_language}")
    
    # Required payment suggestions for Stage 3 - multilingual
    payment_suggestions = {
        'english': ["cash upon delivery", "cash on meetup", "cash on pickup"],
        'tagalog': ["bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"],
        'cebuano': ["bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"]
    }
    
    required_payment_suggestions = payment_suggestions.get(detected_language, payment_suggestions['english'])
    
    # Hard-coded override: Check each suggestion for payment-related content
    for suggestion in suggestions:
        suggestion_lower = suggestion.lower()
        print(f"🔍 DEBUG: Checking suggestion: '{suggestion}' -> lower: '{suggestion_lower}'")
        
        # Check for ANY payment-related keywords
        if ('payment' in suggestion_lower or 
            'bank' in suggestion_lower or 
            'transfer' in suggestion_lower or 
            'method' in suggestion_lower or 
            'prefer' in suggestion_lower or 
            'choice' in suggestion_lower or 
            'option' in suggestion_lower or 
            'accept' in suggestion_lower or 
            'works for you' in suggestion_lower or 
            'okay' in suggestion_lower):
            
            print(f"💳 PAYMENT-RELATED SUGGESTION DETECTED: '{suggestion}' - FORCING CASH OPTIONS")
            return required_payment_suggestions
    
    # If we get here, no payment keywords were found, proceed with normal validation
    print("🔍 DEBUG: No payment keywords detected, proceeding with normal validation")
    
    # Patterns to reject
    forbidden_patterns = [
        r'[0-9]',  # Any digits
        r'[₱$€£]',  # Currency symbols
        r'\b(unit|units|kg|kilo|kilo|pcs|pieces|dozen|dozens|liter|liters|kg|grams)\b',  # Units
        r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand)\b',  # Number words
        r'\b(magkano|tagpila|presyo|price|cost|total|amount)\b',  # Price-related words
        r'\b(bank|transfer|method|prefer|choice|option|payment|accept)\b',  # Payment-related words to block
    ]
    
    filtered_suggestions = []
    rejected_count = 0
    
    for suggestion in suggestions:
        print(f"🔍 Checking: '{suggestion}'")
        
        # Check if suggestion contains any forbidden patterns
        is_valid = True
        for pattern in forbidden_patterns:
            if re.search(pattern, suggestion, re.IGNORECASE):
                print(f"❌ REJECTED: Contains forbidden pattern: {pattern}")
                is_valid = False
                rejected_count += 1
                break
        
        if is_valid:
            print(f"✅ ACCEPTED: '{suggestion}'")
            filtered_suggestions.append(suggestion)
    
    print(f"📊 Validation Results: {len(filtered_suggestions)} accepted, {rejected_count} rejected")
    return filtered_suggestions

@ai_suggestions_bp.route('/generate-contextual-suggestions', methods=['POST', 'OPTIONS'])
def generate_contextual_suggestions():
    """Pure AI-driven contextual suggestions - analyzes conversation and generates 3 best replies"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("🤖 AI-DRIVEN SUGGESTIONS PROCESSING")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract conversation data
        user_role = data.get('userRole', '')
        listing_name = data.get('listingName', '')
        messages = data.get('messages', [])
        detected_language = data.get('detectedLanguage', 'english')
        
        print("=" * 60)
        print(f"👤 User Role: {user_role} ({'SELLER' if user_role == 'livestock_owner' else 'BUYER'})")
        print(f"📋 Listing: {listing_name}")
        print(f"📊 Messages: {len(messages)}")
        print("=" * 60)
        
        # Validate user role
        if user_role not in ['livestock_owner', 'crop_farmer']:
            return jsonify({
                "success": False,
                "error": "Invalid user role. Must be 'livestock_owner' (seller) or 'crop_farmer' (buyer)",
                "suggestions": []
            }), 400
        
        # Format conversation for AI analysis
        conversation_text = ""
        for i, msg in enumerate(messages):
            sender = msg.get('senderName', 'User')
            text = msg.get('text', '')
            role = "Seller" if msg.get('senderRole') == 'livestock_owner' else "Buyer"
            conversation_text += f"{i+1}. {sender} ({role}): {text}\n"
        
        print(f"📝 Conversation for AI analysis:\n{conversation_text}")
        
        # Comprehensive AI prompt for full conversation analysis
        ai_prompt = f"""You are AgriLink's AI conversation assistant for livestock waste and processed waste transactions.

Your task: Generate 3 VERY SHORT, DIRECT replies for the {user_role} that advance the transaction.

CRITICAL: Generate ALL suggestions in {detected_language} language only!

CONVERSATION CONTEXT:
- Listing: {listing_name} (Livestock Waste/Processed Waste)
- User Role: {user_role} ({'SELLER' if user_role == 'livestock_owner' else 'BUYER'})
- Language: {detected_language}
- Current Conversation:
{conversation_text}

IMPORTANT STAGE DETECTION:
- If users are already discussing PRICE, QUANTITY, or UNITS → Skip to Stage 2 (Location/Logistics)
- If users are already discussing LOCATION, PICKUP, or DELIVERY → Skip to Stage 3 (Payment Method)
- If users are already discussing PAYMENT or CASH → Skip to Stage 4 (Confirmation)
- If just starting → Use Stage 1 (Listing Details)

STRICT FORBIDDEN RULES:
- NEVER use ANY numbers (0,1,2,3,4,5,6,7,8,9)
- NEVER mention prices, amounts, quantities
- NEVER use placeholders [like this]
- NEVER mention specific locations
- NEVER mention units or measurements
- NEVER make assumptions about the listing
- NEVER suggest prices, quantities, or locations to users

STAGE-SPECIFIC REPLIES:
Stage 1 (Listing Details): Ask about availability, quality, general interest
Stage 2 (Location/Logistics): Arrange pickup/delivery without specifics
Stage 3 (Payment Method): Suggest ONLY these 3 EXACT phrases:
- English: "cash upon delivery", "cash on meetup", "cash on pickup"
- Tagalog: "bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"
- Cebuano: "bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"
NEVER mention bank transfers, payment methods, or choices
Stage 4 (Confirmation): Confirm agreement and prepare summary
- For livestock owners: Include "Can you prepare the summary for me?" suggestion
- For crop farmers: Regular confirmation messages

SUMMARY GENERATION (Livestock Owner Only):
If user_role is 'livestock_owner' and conversation has ALL required information:
- Buyer name (crop farmer name mentioned in conversation)
- Listing name (provided)
- Listing price (mentioned by buyer or seller)
- Listing quantity with units (mentioned by buyer or seller)
- Mode of payment (cash upon delivery/cash on meetup/cash on pickup)
- Location (meeting/pickup location mentioned)

Generate summary in EXACT format:
buyer name: [name]
listing name: {listing_name}
listing price: [price mentioned]
listing quantity: [quantity mentioned]
mode of payment: [payment method]
location: [meeting/pickup location]

GOOD EXAMPLES:
English:
Stage 1: "Yes, it's available. What do you need?"
Stage 2: "Cash payment works. When can you meet?"
Stage 3: "cash upon delivery", "cash on meetup", "cash on pickup"
Stage 4 (Livestock Owner): "Perfect! I'll prepare your order.", "Can you prepare the summary for me?"
Stage 4 (Crop Farmer): "Perfect! I'll prepare your order.", "Confirmed, let's proceed."

Tagalog:
Stage 1: "Oo, mayroon. Ano ang kailangan mo?"
Stage 2: "Cash payment okay. Kailan ka pwede?"
Stage 3: "bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"
Stage 4 (Livestock Owner): "Perfect! Ihahanda ko ang order mo.", "Pwede mo bang i-prepare ang summary para sa akin?"
Stage 4 (Crop Farmer): "Perfect! Ihahanda ko ang order mo.", "Confirmed, let's proceed."

Cebuano:
Stage 1: "Oo, naay. Unsa ang kinahanglan nimo?"
Stage 2: "Cash payment okay. Kanus-a ka pwede?"
Stage 3: "bayad sa pag-abot", "bayad sa pagkita", "bayad sa pickup"
Stage 4 (Livestock Owner): "Perfect! Ihahando ko ang order nimo.", "Pwede ba nimo i-prepare ang summary para nako?"
Stage 4 (Crop Farmer): "Perfect! Ihahando ko ang order nimo.", "Confirmed, let's proceed."

BAD EXAMPLES (DO NOT USE):
"Yes, it's available for ₱500" ❌
"How many units do you need?" ❌
"I'm at [your location]" ❌
"Price per unit is cheap" ❌

REPLY GUIDELINES:
- Keep VERY SHORT (5-10 words maximum)
- Ask for information you don't know
- Be direct and conversational
- Match the conversation language
- ADVANCE to next stage if current stage is already being discussed
- NEVER suggest prices, quantities, or locations

RETURN FORMAT (JSON ONLY):
{{
  "current_stage": "1|2|3|4",
  "detected_language": "english|tagalog|cebuano",
  "conversation_summary": "Brief summary",
  "next_stage_needed": "What to discuss next",
  "transaction_summary": "Generated summary if all data available (livestock owner only)",
  "suggestions": [
    "Short question 1",
    "Short question 2", 
    "Short question 3"
  ]
}}

Generate ONLY JSON. No explanations."""

        try:
            # Call GPT-4 for comprehensive analysis
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ai_prompt},
                    {"role": "user", "content": f"Analyze this conversation and generate 3 best replies for {user_role}"}
                ],
                max_tokens=500,
                temperature=0.3,  # Lowered for more deterministic stage detection
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content.strip()
            print(f"🤖 AI Analysis Response: {ai_response}")
            
            # Parse AI response
            analysis_data = json.loads(ai_response)
            
            print(f"✅ AI Analysis Complete:")
            print(f"   Stage: {analysis_data.get('current_stage')}")
            print(f"   Language: {analysis_data.get('detected_language')}")
            print(f"   Next Stage: {analysis_data.get('next_stage_needed')}")
            print(f"   Raw Suggestions: {analysis_data.get('suggestions', [])}")
            
            # Validate suggestions to remove numbers, currency, etc.
            raw_suggestions = analysis_data.get('suggestions', [])
            print(f"🔍 DEBUG: Raw AI suggestions before validation: {raw_suggestions}")
            validated_suggestions = validate_suggestions(raw_suggestions, detected_language)
            print(f"🔍 DEBUG: Validated suggestions after validation: {validated_suggestions}")
            
            # Parse transaction summary if provided
            raw_summary = analysis_data.get('transaction_summary', '')
            parsed_summary = parse_transaction_summary(raw_summary)
            print(f"📋 DEBUG: Raw summary: '{raw_summary}'")
            print(f"📋 DEBUG: Parsed summary: {parsed_summary}")
            
            # Check if user requested summary preparation (Stage 4 for livestock owners)
            auto_send_summary = False
            if user_role == 'livestock_owner' and messages:
                last_message = messages[-1].get('text', '').lower().strip()
                summary_requests = [
                    'can you prepare the summary for me?',
                    'pwede mo bang i-prepare ang summary para sa akin?',
                    'pwede ba nimo i-prepare ang summary para nako?'
                ]
                if last_message in summary_requests:
                    print("📋 SUMMARY REQUEST DETECTED - Forcing summary generation")
                    # Force generate summary even if not all fields are present
                    if not parsed_summary:
                        # Generate partial summary from conversation
                        partial_summary = generate_partial_summary(conversation_text, listing_name)
                        parsed_summary = parse_transaction_summary(partial_summary)
                        auto_send_summary = True
                    else:
                        auto_send_summary = True
            
            # If all suggestions were rejected, use fallback
            if len(validated_suggestions) == 0:
                print("⚠️ All AI suggestions rejected, using fallback")
                fallback_suggestions = {
                    "livestock_owner": {
                        'english': ["Yes, it's available. What do you need?", "Cash payment works. When can you meet?", "We can arrange pickup. When are you free?"],
                        'tagalog': ["Oo, mayroon. Ano ang kailangan mo?", "Cash payment okay. Kailan ka pwede?", "Pwede ang pickup. Kailan ka libre?"],
                        'cebuano': ["Oo, naay. Unsa ang kinahanglan nimo?", "Cash payment okay. Kanus-a ka pwede?", "Pwede ang pickup. Kanus-a ka libre?"]
                    },
                    "crop_farmer": {
                        'english': ["Is this still available?", "How much is the price per unit?", "Can we arrange pickup this week?"],
                        'tagalog': ["Available pa ba ito?", "Magkano presyo per unit?", "Pwede ba pickup this week?"],
                        'cebuano': ["Available pa ba ni?", "Tagpila presyo per unit?", "Pwede ba pickup this week?"]
                    }
                }
                
                # Get fallback suggestions for the detected language
                user_fallbacks = fallback_suggestions.get(user_role, fallback_suggestions["livestock_owner"])
                language_fallbacks = user_fallbacks.get(detected_language, user_fallbacks['english'])
                validated_suggestions = language_fallbacks
            
            # Validate and return response
            return jsonify({
                "success": True,
                "stage": analysis_data.get('current_stage', '1'),
                "language": analysis_data.get('detected_language', 'english'),
                "suggestions": validated_suggestions[:3],
                "confidence": 0.95,
                "userRole": user_role,
                "roleType": "seller" if user_role == 'livestock_owner' else "buyer",
                "conversation_summary": analysis_data.get('conversation_summary', ''),
                "next_stage_needed": analysis_data.get('next_stage_needed', ''),
                "summary": parsed_summary,  # Send parsed summary object instead of raw text
                "autoSendSummary": auto_send_summary,  # Flag for frontend to auto-send summary
                "processing_time": f"{time.time() - start_time:.2f}s",
                "ai_driven": True,
                "validation_applied": True
            }), 200
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse AI JSON response: {e}")
            print(f"Raw AI response: {ai_response}")
            
            # Fallback if JSON parsing fails
            return jsonify({
                "success": False,
                "error": "AI response parsing failed",
                "suggestions": [],
                "raw_response": ai_response
            }), 500
            
        except Exception as openai_error:
            print(f"❌ OpenAI API Error: {openai_error}")
            
            # Simple fallback suggestions
            fallback_suggestions = {
                "livestock_owner": {
                    'english': ["Yes, it's available. What do you need?", "Cash payment works. When can you meet?", "We can arrange pickup. When are you free?"],
                    'tagalog': ["Oo, mayroon. Ano ang kailangan mo?", "Cash payment okay. Kailan ka pwede?", "Pwede ang pickup. Kailan ka libre?"],
                    'cebuano': ["Oo, naay. Unsa ang kinahanglan nimo?", "Cash payment okay. Kanus-a ka pwede?", "Pwede ang pickup. Kanus-a ka libre?"]
                },
                "crop_farmer": {
                    'english': ["Is this still available?", "How much is the price per unit?", "Can we arrange pickup this week?"],
                    'tagalog': ["Available pa ba ito?", "Magkano presyo per unit?", "Pwede ba pickup this week?"],
                    'cebuano': ["Available pa ba ni?", "Tagpila presyo per unit?", "Pwede ba pickup this week?"]
                }
            }
            
            # Get fallback suggestions for the detected language
            user_fallbacks = fallback_suggestions.get(user_role, fallback_suggestions["livestock_owner"])
            language_fallbacks = user_fallbacks.get(detected_language, user_fallbacks['english'])
            
            return jsonify({
                "success": True,
                "stage": "1",
                "language": detected_language,
                "suggestions": language_fallbacks,
                "confidence": 0.3,
                "fallback_used": True,
                "processing_time": f"{time.time() - start_time:.2f}s"
            }), 200
        
    except Exception as e:
        print(f"❌ Error in AI suggestions: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "suggestions": []
        }), 500
