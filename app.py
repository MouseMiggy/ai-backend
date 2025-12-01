from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import json
import time
import base64
import requests
import os
from datetime import datetime
from ai_suggestion import ai_suggestions_bp, init_openai

app = Flask(__name__)
# Allow all origins for local development (mobile devices need this)
# Flask-CORS removed - using manual CORS headers instead to avoid conflicts

# Log all incoming requests for debugging
@app.before_request
def log_request_info():
    print(f"\n{'='*60}")
    print(f"📥 INCOMING REQUEST: {request.method} {request.path}")
    print(f"📍 From: {request.remote_addr}")
    print(f"🌐 Origin: {request.headers.get('Origin', 'None')}")
    print(f"🔗 User-Agent: {request.headers.get('User-Agent', 'None')[:50]}")
    if request.method == 'POST':
        print(f"📦 Content-Type: {request.headers.get('Content-Type', 'None')}")
        try:
            data = request.get_json(silent=True) or {}
            print(f" Has JSON data: {bool(data)}")
            if data:
                print(f" Keys: {list(data.keys())[:5]}")
        except:
            pass
    print(f"{'='*60}\n")

# Add CORS headers to all responses - Final deployment fix for 405 errors
@app.after_request
def add_cors_headers(response):
    print(f" OUTGOING RESPONSE: {response.status_code} for {request.method} {request.path}")
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Max-Age'] = '86400'  # 24 hours
    print(f" Added CORS headers for origin: {origin}")
    return response

# Handle OPTIONS requests explicitly for all routes
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    print(f" Handling OPTIONS request for: /{path}")
    response = make_response('', 200)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response

# Initialize OpenAI client
# Note: Using compatible versions of openai and httpx to avoid 'proxies' argument error
openai_api_key = os.environ.get('OPENAI_API_KEY', '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')

# Global OpenAI client for report validation
global client
client = openai.OpenAI(api_key=openai_api_key)

# Initialize OpenAI client and AI suggestions
init_openai(openai_api_key)

# Register AI suggestions blueprint
app.register_blueprint(ai_suggestions_bp)
print("OpenAI client initialized successfully")

def download_image_to_base64(image_url):
    """Download image from URL and convert to base64 for OpenAI"""
    try:
        print(f" Downloading image: {image_url[:80]}...")
        print(f"📥 Downloading image: {image_url[:80]}...")
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()
        
        # Get content type
        content_type = response.headers.get('content-type', 'image/jpeg')
        if 'image' not in content_type:
            raise ValueError(f"URL does not point to an image: {content_type}")
        
        # Read image data
        image_data = response.content
        
        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine MIME type
        mime_type = content_type
        if mime_type == 'image/jpg':
            mime_type = 'image/jpeg'
        
        # Return data URL format
        data_url = f"data:{mime_type};base64,{base64_image}"
        print(f"✅ Image downloaded and converted to base64 ({len(base64_image)} chars)")
        return data_url
        
    except Exception as e:
        print(f"❌ Error downloading image {image_url[:80]}: {str(e)}")
        raise

@app.route('/validate-report', methods=['POST', 'OPTIONS'])
def validate_report():
    """Validate user reports for inappropriate content using AI"""
    print(f"📥 REQUEST: {request.method} /validate-report")
    print(f"🌐 Origin: {request.headers.get('Origin', 'None')}")
    print(f"🔧 Content-Type: {request.headers.get('Content-Type', 'None')}")
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("INCOMING REPORT VALIDATION REQUEST")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract data
        caption = data.get('caption', '')
        media_url = data.get('mediaUrl', '') or data.get('media_url', '')
        image_urls = data.get('imageUrls', []) or []
        report_type = data.get('reportType', 'spam')
        additional_note = data.get('additionalNote', '') or data.get('additional_note', '')
        
        # Process imageUrls array - get all valid image URLs
        all_image_urls = []
        if isinstance(image_urls, list) and len(image_urls) > 0:
            for img in image_urls:
                if isinstance(img, str) and img.strip():
                    all_image_urls.append(img.strip())
                elif isinstance(img, dict) and img.get('url') and img['url'].strip():
                    all_image_urls.append(img['url'].strip())
        # Also add media_url if it's not already in the array
        if media_url and media_url.strip() and media_url.strip() not in all_image_urls:
            all_image_urls.append(media_url.strip())
        
        print(f"Caption: {caption[:100] if caption else 'Empty'}")
        print(f"Image URLs: {len(all_image_urls)} image(s)")
        print(f"Report Type: {report_type}")
        print(f"Has Images: {len(all_image_urls) > 0}")
        
        # All reports go directly to AI validation
        print("Calling OpenAI for detailed analysis...")
        
        # Prepare content for OpenAI - simple and direct
        user_content = [{"type": "text", "text": f"""Text: "{caption}"

Check for bad words first. If found, mark VALID. If no bad words, check if text is about agriculture.

Bad words (English/Tagalog/Bisaya): buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.

Examples:
- "buang fruits" → VALID (has "buang")
- "fruits vegetables" → Check if agriculture-related
"""}]
        
        print(f"DEBUG: User content text being sent to AI: {user_content[0]['text'][:300]}")
        
        # Add all images to the request - download and convert to base64
        images_processed = 0
        if len(all_image_urls) > 0:
            print(f"📸 Processing {len(all_image_urls)} image(s) for OpenAI analysis")
            for index, img_url in enumerate(all_image_urls):
                try:
                    # Download image and convert to base64
                    base64_image_url = download_image_to_base64(img_url)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": base64_image_url}
                    })
                    images_processed += 1
                    print(f"✅ Image {index + 1} downloaded and added to OpenAI request")
                except Exception as img_error:
                    print(f"⚠️ Error processing image {index + 1} ({img_url[:50]}...): {img_error}")
                    # Continue with other images even if one fails
        
        # Create prompt for analyzing multiple images
        image_count = len(all_image_urls)
        image_analysis_instructions = ""
        if image_count > 0:
            image_list = "\n".join([f'Image {i + 1}: [detailed analysis of what this image shows]' for i in range(image_count)])
            image_analysis_instructions = f"""
**CRITICAL: IMAGE-BY-IMAGE ANALYSIS REQUIRED**

You must analyze EACH image individually and describe what you see in each one.

**IMAGE ANALYSIS FORMAT:**
For posts with multiple images, you MUST analyze each image separately and describe each one clearly in your reason field.

Format your analysis as:
{image_list}

For EACH image, you must state:
1. What the image shows (be specific and descriptive)
2. Whether it is agriculture-related (YES/NO)
3. Why this specific image makes the report valid or invalid

**EXAMPLE FORMAT:**
If there are 3 images:
- "Image 1: Shows a field of corn crops with green leaves, clearly agriculture-related. Report is INVALID for this image."
- "Image 2: Shows a city street with cars and buildings, NOT agriculture-related. Report is VALID for this image."
- "Image 3: Shows a farmer with livestock, clearly agriculture-related. Report is INVALID for this image."

**CRITICAL RULE: If ANY single image is NOT agriculture-related or violates community standards, the ENTIRE post report must be marked as VALID (violation).**
"""
        
        # Build reason instruction based on image count - provide comprehensive, detailed explanations
        if image_count > 0:
            reason_instruction = """Provide a comprehensive, detailed explanation (at least 4-5 sentences) covering:
1. Text content analysis: Analyze the text word-by-word. If offensive words are found (English/Tagalog/Bisaya), specify exactly which words were detected and explain why they are offensive (e.g., "buang" is a Bisaya profanity meaning "crazy" or "insane", "bobo" is a Tagalog insult meaning "stupid"). If no offensive words, describe what the text is about and whether it relates to agriculture.
2. For EACH image: Provide a detailed description of what you see in the image. Be specific about objects, scenes, people, animals, plants, or any content visible. State clearly whether the image shows agricultural content (crops, livestock, farming equipment, gardens, soil, etc.) or non-agricultural content (city scenes, vehicles, buildings, unrelated objects, etc.). Explain how each image relates to the report validity.
3. Overall assessment: Synthesize all findings (text + all images). Explain why the verdict is VALID (violation found) or INVALID (no violation, legitimate content) based on ALL factors analyzed. CRITICAL: If ANY image is non-agricultural or contains violations, the verdict MUST be VALID. If ALL content is legitimate agriculture-related, the verdict MUST be INVALID.
4. Specific violations or legitimacy: If verdict is VALID, list ALL specific violations found (exact offensive words, which images are non-agricultural, etc.). If verdict is INVALID, explain why the content is legitimate agricultural content with specific examples from both text and images.
Format: "Text Analysis: [detailed analysis of text content, offensive words if any, agricultural relevance]. Image 1 Analysis: [detailed description of what image 1 shows, whether agricultural, why valid/invalid]. Image 2 Analysis: [detailed description of what image 2 shows, whether agricultural, why valid/invalid]. Overall Assessment: [comprehensive conclusion explaining all reasons for the verdict (VALID or INVALID) based on text and all images]." """
        else:
            reason_instruction = """Provide a comprehensive, detailed explanation (at least 3-4 sentences) covering:
1. Text content analysis: Analyze the text word-by-word. If offensive words are found (English/Tagalog/Bisaya), specify exactly which words were detected and explain why they are considered offensive (e.g., "buang" is a Bisaya profanity meaning "crazy" or "insane", "bobo" is a Tagalog insult meaning "stupid"). If no offensive words, describe what the text says and the context.
2. Agricultural relevance: Whether the content relates to farming, crops, livestock, or agricultural activities, with specific examples from the text. Explain what agricultural topics are discussed (if any).
3. Violation assessment: If verdict is VALID (violation found), list ALL specific violations found (exact offensive words, why content is not agriculture-related, etc.). If verdict is INVALID (no violation), explain why the content is legitimate and agriculture-related with specific examples.
4. Overall conclusion: A clear summary explaining ALL the reasons why the verdict is VALID (violation found) or INVALID (no violation, legitimate content) based on the comprehensive analysis."""
        
        prompt = f"""You are AgriLink's content moderator. Validate post reports.

CRITICAL: VALID = violation found (content should be removed). INVALID = no violation (legitimate content).

RULES (apply in order):
1. Check for bad words FIRST (English/Tagalog/Bisaya): buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.
   - If bad word found → VERDICT MUST BE "VALID" (violation found)
   - Example: "buang fruits" → VALID

2. If no bad words, check if text is about agriculture:
   - Text about farming/crops/livestock/agriculture → Continue to image check
   - Text NOT about agriculture → VERDICT MUST BE "VALID" (violation: irrelevant content)

3. If images present:
   - If ANY single image is NOT agriculture-related → VERDICT MUST BE "VALID" (violation: non-agricultural image)
   - If ALL images are agriculture-related AND text is agriculture-related → VERDICT MUST BE "INVALID" (no violation)

CRITICAL LOGIC: 
- If you find ANY violation (bad words, non-agricultural text, or non-agricultural image), the verdict MUST be "VALID"
- Only mark as "INVALID" if ALL content (text + all images) is legitimate agriculture-related content with no violations

{image_analysis_instructions}

Return JSON:
{{
  "verdict": "VALID" or "INVALID",
  "confidence": 0.0-1.0,
  "reason": "{reason_instruction}",
  "category": "spam|offensive|misinformation|irrelevant|false_report",
  "severity": "low|medium|high",
  "action_recommended": "none|warning|content_removal|user_suspension"
}}

IMPORTANT: The reason field must be comprehensive and detailed (at least 3-4 sentences for text-only, 4-5 sentences for posts with images), explaining ALL factors that led to the verdict. Do not use brief or one-sentence reasons. Always provide detailed explanations covering text analysis, image analysis (if applicable), and overall assessment.
"""
        
        # Call OpenAI with your exact prompt
        print(" Calling OpenAI API with vision support...")
        print(f" Content items: {len(user_content)} (text: 1, images: {len(all_image_urls)})")
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                max_tokens=1200,  # Increased for detailed image-by-image analysis
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            print(f" OpenAI Response received: {ai_response[:200]}...")
            
            validation_result = json.loads(ai_response)
            
            # Ensure required fields exist
            if not validation_result.get('verdict'):
                raise Exception("OpenAI response missing verdict field")
            
            # Validate verdict
            if validation_result['verdict'] not in ['VALID', 'INVALID']:
                print(" Invalid verdict from OpenAI, defaulting to INVALID")
                validation_result['verdict'] = 'INVALID'
            
            # CRITICAL: Check if reason text contradicts verdict and correct it
            # If reason says "verdict is VALID" or "overall verdict is VALID" but verdict is INVALID, correct it
            reason_text = validation_result.get('reason', '').lower()
            current_verdict = validation_result.get('verdict', 'INVALID')
            
            # Check for explicit statements in reason that indicate VALID verdict
            reason_indicates_valid = (
                'verdict is valid' in reason_text or
                'overall verdict is valid' in reason_text or
                'the verdict is valid' in reason_text or
                'must be valid' in reason_text or
                'verdict must be "valid"' in reason_text or
                'report is valid' in reason_text or
                'overall verdict is valid' in reason_text
            )
            
            # Check for explicit statements in reason that indicate INVALID verdict
            reason_indicates_invalid = (
                'verdict is invalid' in reason_text or
                'overall verdict is invalid' in reason_text or
                'the verdict is invalid' in reason_text or
                'must be invalid' in reason_text or
                'verdict must be "invalid"' in reason_text or
                'report is invalid' in reason_text or
                'overall verdict is invalid' in reason_text
            )
            
            # If reason clearly indicates VALID but verdict is INVALID, correct it
            if reason_indicates_valid and current_verdict == 'INVALID':
                print("⚠️ WARNING: Reason indicates VALID but verdict is INVALID. Correcting verdict to VALID.")
                validation_result['verdict'] = 'VALID'
            # If reason clearly indicates INVALID but verdict is VALID, correct it
            elif reason_indicates_invalid and current_verdict == 'VALID':
                print("⚠️ WARNING: Reason indicates INVALID but verdict is VALID. Correcting verdict to INVALID.")
                validation_result['verdict'] = 'INVALID'
            
            # Ensure reason is clean and only contains the validation reasons
            if validation_result.get('reason'):
                # Remove any verbose prefixes or extra text
                validation_result['reason'] = validation_result['reason'].strip()
            
            print(f" FINAL RESULT: {json.dumps(validation_result, indent=2)}")
            
            return jsonify({
                "status": "success",
                "result": validation_result,
                "processing_time": f"{time.time() - start_time:.2f}s",
                "image_analyzed": len(all_image_urls) > 0,
                "images_analyzed": len(all_image_urls)
            }), 200
        except Exception as openai_error:
            print(f" OpenAI API Error: {openai_error}")
            raise
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# Comment and message reports now use /validate-report endpoint
# Removed separate endpoints - they use the same validation as posts

@app.route('/validate-listing-report', methods=['POST', 'OPTIONS'])
def validate_listing_report():
    # Handle CORS preflight - CORS() already handles headers, just return 200
    if request.method == 'OPTIONS':
        return '', 200
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("INCOMING LISTING REPORT VALIDATION REQUEST")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract data
        listing_name = data.get('listingName', '') or data.get('name', '') or data.get('title', '')
        listing_details = data.get('listingDetails', '') or data.get('details', '') or data.get('description', '')
        image_url = data.get('imageUrl', '') or data.get('image', '') or data.get('mediaUrl', '')
        image_urls = data.get('imageUrls', []) or []
        report_type = data.get('reportType', 'spam')
        additional_note = data.get('additionalNote', '') or data.get('additional_note', '')
        
        # Process imageUrls array
        all_image_urls = []
        if isinstance(image_urls, list) and len(image_urls) > 0:
            for img in image_urls:
                if isinstance(img, str) and img.strip():
                    all_image_urls.append(img.strip())
                elif isinstance(img, dict) and img.get('url') and img['url'].strip():
                    all_image_urls.append(img['url'].strip())
        # Also add image_url if it's not already in the array
        if image_url and image_url.strip() and image_url.strip() not in all_image_urls:
            all_image_urls.append(image_url.strip())
        
        print(f"Listing Name: {listing_name[:100] if listing_name else 'Empty'}")
        print(f"Listing Details: {listing_details[:100] if listing_details else 'Empty'}")
        print(f"Image URLs: {len(all_image_urls)} image(s)")
        print(f"Report Type: {report_type}")
        
        # Prepare content for OpenAI
        user_content = [{"type": "text", "text": f"""Listing Name: "{listing_name}"
Listing Details: "{listing_details}"

Check for bad words first. If found → VALID. If no bad words, check if name/details/images are agriculture-related.
"""}]
        
        print(f"DEBUG: User content text being sent to AI: {user_content[0]['text'][:300]}")
        
        # Add all images to the request - download and convert to base64
        images_processed = 0
        if len(all_image_urls) > 0:
            print(f"📸 Processing {len(all_image_urls)} image(s) for OpenAI analysis")
            for index, img_url in enumerate(all_image_urls):
                try:
                    # Download image and convert to base64
                    base64_image_url = download_image_to_base64(img_url)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": base64_image_url}
                    })
                    images_processed += 1
                    print(f"✅ Image {index + 1} downloaded and added to OpenAI request")
                except Exception as img_error:
                    print(f"⚠️ Error processing image {index + 1} ({img_url[:50]}...): {img_error}")
                    # Continue with other images even if one fails
        
        # Create prompt for listing validation
        image_count = len(all_image_urls)
        image_analysis_instructions = ""
        if image_count > 0:
            image_list = "\n".join([f'image {i + 1}: [analysis of this image]' for i in range(image_count)])
            image_analysis_instructions = f"""
**IMAGE ANALYSIS FORMAT:**
Analyze each image separately and format your response as:
{image_list}

For each image, state:
- What you see in the image
- Whether it is agriculture-related (livestock, crops, farming equipment, etc.) (YES/NO)
- Why the report is valid or invalid based on this image
"""
        
        # Build reason instruction based on image count - provide comprehensive, detailed explanations
        if image_count > 0:
            reason_instruction = """Provide a comprehensive, detailed explanation (at least 4-5 sentences) covering:
1. Listing name and details analysis: Analyze the listing name and details word-by-word. If offensive words are found (English/Tagalog/Bisaya), specify exactly which words were detected and explain why they are offensive. If no offensive words, describe what the listing name and details say and whether they relate to agriculture (livestock, crops, farming equipment, etc.).
2. For EACH image: Provide a detailed description of what you see in the image. Be specific about objects, scenes, animals, plants, equipment, or any content visible. State clearly whether the image shows agricultural content (livestock, crops, farming equipment, agricultural settings, gardens, soil, etc.) or non-agricultural content (unrelated objects, scenes, etc.). Explain how each image relates to the report validity.
3. Overall assessment: Synthesize all findings (name + details + all images). Explain why the verdict is VALID (violation found) or INVALID (no violation, legitimate content) based on ALL factors analyzed. CRITICAL: If ANY image is non-agricultural or contains violations, the verdict MUST be VALID. If ALL content is legitimate agriculture-related, the verdict MUST be INVALID.
4. Specific violations or legitimacy: If verdict is VALID, list ALL specific violations found (exact offensive words, which images are non-agricultural, why name/details are not agriculture-related, etc.). If verdict is INVALID, explain why the listing is legitimate agricultural content with specific examples from name, details, and all images.
Format: "Listing Name/Details Analysis: [detailed analysis of name and details, offensive words if any, agricultural relevance]. Image 1 Analysis: [detailed description of what image 1 shows, whether agricultural, why valid/invalid]. Image 2 Analysis: [detailed description of what image 2 shows, whether agricultural, why valid/invalid]. Overall Assessment: [comprehensive conclusion explaining all reasons for the verdict (VALID or INVALID) based on name, details, and all images]." """
        else:
            reason_instruction = """Provide a comprehensive, detailed explanation (at least 3-4 sentences) covering:
1. Listing name and details analysis: Analyze the listing name and details word-by-word. If offensive words are found (English/Tagalog/Bisaya), specify exactly which words were detected and explain why they are considered offensive. If no offensive words, describe what the listing name and details say and the context.
2. Agricultural relevance: Whether the listing relates to farming, livestock, crops, or agricultural activities, with specific examples from the name and details. Explain what agricultural topics are discussed (if any).
3. Violation assessment: If verdict is VALID (violation found), list ALL specific violations found (exact offensive words, why name/details are not agriculture-related, etc.). If verdict is INVALID (no violation), explain why the listing is legitimate and agriculture-related with specific examples.
4. Overall conclusion: A clear summary explaining ALL the reasons why the verdict is VALID (violation found) or INVALID (no violation, legitimate content) based on the comprehensive analysis."""
        
        prompt = f"""You are AgriLink's content moderator for listings.

CRITICAL: VALID = violation found (content should be removed). INVALID = no violation (legitimate content).

RULES (apply in order):
1. Check for bad words FIRST (buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity):
   - If bad word found → VERDICT MUST BE "VALID" (violation found)

2. If no bad words, check if listing name/details are about agriculture:
   - Name/details about farming/livestock/crops/agriculture → Continue to image check
   - Name/details NOT about agriculture → VERDICT MUST BE "VALID" (violation: irrelevant content)

3. If images present:
   - If ANY single image is NOT agriculture-related → VERDICT MUST BE "VALID" (violation: non-agricultural image)
   - If ALL images are agriculture-related AND name/details are agriculture-related → VERDICT MUST BE "INVALID" (no violation)

CRITICAL LOGIC: 
- If you find ANY violation (bad words, non-agricultural name/details, or non-agricultural image), the verdict MUST be "VALID"
- Only mark as "INVALID" if ALL content (name + details + all images) is legitimate agriculture-related content with no violations

{image_analysis_instructions}

Return JSON:
{{
  "verdict": "VALID" or "INVALID",
  "confidence": 0.0-1.0,
  "reason": "{reason_instruction}",
  "category": "spam|offensive|misinformation|irrelevant|false_report",
  "severity": "low|medium|high",
  "action_recommended": "none|warning|content_removal|user_suspension"
}}

IMPORTANT: The reason field must be comprehensive and detailed (at least 3-4 sentences for text-only, 4-5 sentences for listings with images), explaining ALL factors that led to the verdict. Do not use brief or one-sentence reasons. Always provide detailed explanations covering listing name/details analysis, image analysis (if applicable), and overall assessment.
"""
        
        # Call OpenAI
        print(" Calling OpenAI API with vision support for listing validation...")
        print(f" Content items: {len(user_content)} (text: 1, images: {len(all_image_urls)})")
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                max_tokens=1500,  # Increased for comprehensive, detailed explanations with image analysis
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            print(f" OpenAI Response received: {ai_response[:200]}...")
            
            validation_result = json.loads(ai_response)
            
            # Ensure required fields exist
            if not validation_result.get('verdict'):
                raise Exception("OpenAI response missing verdict field")
            
            # Validate verdict
            if validation_result['verdict'] not in ['VALID', 'INVALID']:
                print(" Invalid verdict from OpenAI, defaulting to INVALID")
                validation_result['verdict'] = 'INVALID'
            
            # CRITICAL: Check if reason text contradicts verdict and correct it
            # If reason says "verdict is VALID" or "overall verdict is VALID" but verdict is INVALID, correct it
            reason_text = validation_result.get('reason', '').lower()
            current_verdict = validation_result.get('verdict', 'INVALID')
            
            # Check for explicit statements in reason that indicate VALID verdict
            reason_indicates_valid = (
                'verdict is valid' in reason_text or
                'overall verdict is valid' in reason_text or
                'the verdict is valid' in reason_text or
                'must be valid' in reason_text or
                'verdict must be "valid"' in reason_text or
                'report is valid' in reason_text or
                'overall verdict is valid' in reason_text
            )
            
            # Check for explicit statements in reason that indicate INVALID verdict
            reason_indicates_invalid = (
                'verdict is invalid' in reason_text or
                'overall verdict is invalid' in reason_text or
                'the verdict is invalid' in reason_text or
                'must be invalid' in reason_text or
                'verdict must be "invalid"' in reason_text or
                'report is invalid' in reason_text or
                'overall verdict is invalid' in reason_text
            )
            
            # If reason clearly indicates VALID but verdict is INVALID, correct it
            if reason_indicates_valid and current_verdict == 'INVALID':
                print("⚠️ WARNING: Reason indicates VALID but verdict is INVALID. Correcting verdict to VALID.")
                validation_result['verdict'] = 'VALID'
            # If reason clearly indicates INVALID but verdict is VALID, correct it
            elif reason_indicates_invalid and current_verdict == 'VALID':
                print("⚠️ WARNING: Reason indicates INVALID but verdict is VALID. Correcting verdict to INVALID.")
                validation_result['verdict'] = 'INVALID'
            
            # Ensure reason is clean
            if validation_result.get('reason'):
                validation_result['reason'] = validation_result['reason'].strip()
            
            print(f" FINAL RESULT: {json.dumps(validation_result, indent=2)}")
            
            return jsonify({
                "status": "success",
                "result": validation_result,
                "processing_time": f"{time.time() - start_time:.2f}s",
                "image_analyzed": len(all_image_urls) > 0,
                "images_analyzed": len(all_image_urls),
                "content_type": "listing"
            }), 200
        except Exception as openai_error:
            print(f" OpenAI API Error: {openai_error}")
            raise
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/validate-comment-report', methods=['POST', 'OPTIONS'])
def validate_comment_report():
    """Validate comment reports - focuses on offensive content, not agricultural relevance"""
    # Handle CORS preflight - CORS() already handles headers, just return 200
    if request.method == 'OPTIONS':
        return '', 200
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("INCOMING COMMENT REPORT VALIDATION REQUEST")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract data
        comment_text = data.get('caption', '') or data.get('commentText', '') or data.get('text', '')
        report_type = data.get('reportType', 'spam')
        additional_note = data.get('additionalNote', '') or data.get('additional_note', '')
        
        print(f"Comment Text: {comment_text[:100] if comment_text else 'Empty'}")
        print(f"Report Type: {report_type}")
        
        # Prepare content for OpenAI
        user_content = [{"type": "text", "text": f"""Comment: "{comment_text}"

Check for bad words: buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.

If bad word found → VALID (reason: "Contains offensive language: '[word]'")
If no bad words → INVALID (reason: "No violations found")
"""}]
        
        print(f"DEBUG: User content text being sent to AI: {user_content[0]['text'][:300]}")
        
        prompt = """You are AgriLink's content moderator for comments.

Check for bad words (English/Tagalog/Bisaya): buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.

If bad word found → VALID. If clean → INVALID.

Return JSON:
{
  "verdict": "VALID" or "INVALID",
  "confidence": 0.0-1.0,
  "reason": "Provide a comprehensive, detailed explanation (at least 3-4 sentences) covering: 1. Language analysis: Analyze the comment text word-by-word, checking for offensive language in English, Tagalog, and Bisaya. If offensive words are found, specify exactly which words were detected and explain why they are considered offensive (e.g., 'buang' is a Bisaya profanity meaning 'crazy' or 'insane', 'bobo' is a Tagalog insult meaning 'stupid'). 2. Context assessment: Evaluate the context in which the language is used - whether it's used in a harassing, bullying, or hateful manner, or if it's acceptable usage. 3. Violation details: If VALID, list all specific violations found (exact offensive words, type of harassment, etc.). If INVALID, explain why the comment is acceptable despite potentially strong language. 4. Overall conclusion: Provide a clear summary explaining all reasons for the verdict based on the comprehensive analysis.",
  "category": "harassment|offensive|false_report",
  "severity": "low|medium|high",
  "action_recommended": "none|warning|content_removal|user_suspension"
}

IMPORTANT: The reason field must be comprehensive and detailed (at least 3-4 sentences), explaining ALL factors that led to the verdict. Do not use brief or one-sentence reasons. Always provide detailed explanations covering language analysis, context assessment, and overall conclusion.
"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=800,  # Increased for comprehensive, detailed explanations
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            validation_result = json.loads(ai_response)
            
            if not validation_result.get('verdict'):
                raise Exception("OpenAI response missing verdict field")
            
            if validation_result['verdict'] not in ['VALID', 'INVALID']:
                validation_result['verdict'] = 'INVALID'
            
            if validation_result.get('reason'):
                validation_result['reason'] = validation_result['reason'].strip()
            
            return jsonify({
                "status": "success",
                "result": validation_result,
                "processing_time": f"{time.time() - start_time:.2f}s",
                "content_type": "comment"
            }), 200
        except Exception as openai_error:
            print(f"OpenAI API Error: {openai_error}")
            raise
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/validate-message-report', methods=['POST', 'OPTIONS'])
def validate_message_report():
    """Validate message reports - focuses on offensive content, not agricultural relevance"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({"status": "ok"})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("INCOMING MESSAGE REPORT VALIDATION REQUEST")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract data
        message_text = data.get('caption', '') or data.get('messageText', '') or data.get('text', '')
        report_type = data.get('reportType', 'spam')
        additional_note = data.get('additionalNote', '') or data.get('additional_note', '')
        
        print(f"Message Text: {message_text[:100] if message_text else 'Empty'}")
        print(f"Report Type: {report_type}")
        
        if not message_text or message_text.strip() == '':
            return jsonify({
                "status": "error",
                "error": "Message text is required for validation"
            }), 400
        
        # Prepare content for OpenAI
        user_content = [{"type": "text", "text": f"""Message: "{message_text}"

Check for bad words: buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.

If bad word found → VALID (reason: "Contains offensive language: '[word]'")
If no bad words → INVALID (reason: "No violations found")
"""}]
        
        print(f"DEBUG: User content text being sent to AI: {user_content[0]['text'][:300]}")
        
        prompt = """You are AgriLink's content moderator for messages.

Check for bad words (English/Tagalog/Bisaya): buang, bogo, yawa, gago, putang ina, bobo, tanga, ulol, puta, gagu, profanity, swear words.

If bad word found → VALID. If clean → INVALID.

Return JSON:
{
  "verdict": "VALID" or "INVALID",
  "confidence": 0.0-1.0,
  "reason": "Provide a comprehensive, detailed explanation (at least 3-4 sentences) covering: 1. Language analysis: Analyze the message text word-by-word, checking for offensive language in English, Tagalog, and Bisaya. If offensive words are found, specify exactly which words were detected and explain why they are considered offensive (e.g., 'buang' is a Bisaya profanity meaning 'crazy' or 'insane', 'bobo' is a Tagalog insult meaning 'stupid'). 2. Context assessment: Evaluate the context in which the language is used - whether it's used in a harassing, bullying, threatening, or hateful manner, or if it's acceptable usage. 3. Violation details: If VALID, list all specific violations found (exact offensive words, type of harassment, threats, etc.). If INVALID, explain why the message is acceptable and does not violate community standards. 4. Overall conclusion: Provide a clear summary explaining all reasons for the verdict based on the comprehensive analysis.",
  "category": "harassment|offensive|false_report",
  "severity": "low|medium|high",
  "action_recommended": "none|warning|content_removal|user_suspension"
}

IMPORTANT: The reason field must be comprehensive and detailed (at least 3-4 sentences), explaining ALL factors that led to the verdict. Do not use brief or one-sentence reasons. Always provide detailed explanations covering language analysis, context assessment, and overall conclusion.
"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=800,  # Increased for comprehensive, detailed explanations
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            validation_result = json.loads(ai_response)
            
            if not validation_result.get('verdict'):
                raise Exception("OpenAI response missing verdict field")
            
            if validation_result['verdict'] not in ['VALID', 'INVALID']:
                validation_result['verdict'] = 'INVALID'
            
            if validation_result.get('reason'):
                validation_result['reason'] = validation_result['reason'].strip()
            
            return jsonify({
                "status": "success",
                "result": validation_result,
                "processing_time": f"{time.time() - start_time:.2f}s",
                "content_type": "message"
            }), 200
        except Exception as openai_error:
            print(f"OpenAI API Error: {openai_error}")
            raise
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/validate-listing-image', methods=['POST', 'OPTIONS'])
def validate_listing_image():
    """Validate livestock listing images to verify if they contain livestock waste or processed fertilizer"""
    print(f"📥 REQUEST: {request.method} /validate-listing-image")
    print(f"🌐 Origin: {request.headers.get('Origin', 'None')}")
    print(f"🔧 Content-Type: {request.headers.get('Content-Type', 'None')}")
    
    start_time = time.time()
    
    try:
        data = request.get_json()
        print("INCOMING LISTING IMAGE VALIDATION REQUEST")
        print(f"Request data: {json.dumps(data, indent=2)}")
        
        # Extract data
        image_url = data.get('imageUrl', '') or data.get('image', '')
        image_urls = data.get('imageUrls', []) or []
        listing_name = data.get('listingName', '') or data.get('name', '')
        listing_details = data.get('listingDetails', '') or data.get('details', '')
        
        # Process imageUrls array
        all_image_urls = []
        if isinstance(image_urls, list) and len(image_urls) > 0:
            for img in image_urls:
                if isinstance(img, str) and img.strip():
                    all_image_urls.append(img.strip())
                elif isinstance(img, dict) and img.get('url') and img['url'].strip():
                    all_image_urls.append(img['url'].strip())
        # Also add image_url if it's not already in the array
        if image_url and image_url.strip() and image_url.strip() not in all_image_urls:
            all_image_urls.append(image_url.strip())
        
        print(f"Listing Name: {listing_name[:100] if listing_name else 'Empty'}")
        print(f"Listing Details: {listing_details[:100] if listing_details else 'Empty'}")
        print(f"Image URLs: {len(all_image_urls)} image(s)")
        
        if len(all_image_urls) == 0:
            return jsonify({
                "status": "error",
                "error": "No images provided for validation"
            }), 400
        
        # Prepare content for OpenAI
        user_content = [{"type": "text", "text": f"""Listing Name: "{listing_name}"
Listing Details: "{listing_details}"

Analyze the images to determine if they show legitimate livestock waste or processed fertilizer suitable for agricultural use.
"""}]
        
        print(f"DEBUG: User content text being sent to AI: {user_content[0]['text'][:300]}")
        
        # Add all images to the request - download and convert to base64
        images_processed = 0
        if len(all_image_urls) > 0:
            print(f"📸 Processing {len(all_image_urls)} image(s) for OpenAI analysis")
            for index, img_url in enumerate(all_image_urls):
                try:
                    # Download image and convert to base64
                    base64_image_url = download_image_to_base64(img_url)
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": base64_image_url}
                    })
                    images_processed += 1
                    print(f"✅ Image {index + 1} downloaded and added to OpenAI request")
                except Exception as img_error:
                    print(f"⚠️ Error processing image {index + 1} ({img_url[:50]}...): {img_error}")
                    # Continue with other images even if one fails
        
        prompt = f"""You are AgriLink's livestock waste verification expert. Analyze images to verify if they show legitimate livestock waste or processed fertilizer.

CRITICAL: 
- VERIFIED_LEGITIMATE = Image shows genuine livestock waste or processed fertilizer suitable for agricultural use
- VERIFIED_NOT_LEGITIMATE = Image is verified but does NOT show livestock waste or processed fertilizer
- UNABLE_TO_VERIFY = Cannot determine due to poor image quality, unclear content, or technical issues

VERIFICATION RULES:
1. VERIFIED_LEGITIMATE if image shows:
   - Animal manure/feces (cow, pig, chicken, carabao, etc.)
   - Composted organic waste from livestock
   - Processed fertilizer pellets or granules
   - Organic fertilizer in bags, containers, or piles
   - Vermicompost or worm castings
   - Any clear agricultural waste/fertilizer products

2. VERIFIED_NOT_LEGITIMATE if image shows:
   - Regular garbage, plastic, or non-organic waste
   - Food waste, kitchen scraps, or household trash
   - Construction materials, chemicals, or industrial waste
   - Unrelated objects, vehicles, buildings, or people
   - Clear non-agricultural content

3. UNABLE_TO_VERIFY if image:
   - Is too blurry, dark, or low quality to identify content
   - Shows unclear or ambiguous content
   - Is too zoomed in or cropped to identify context
   - Has technical issues preventing analysis

IMAGE ANALYSIS FORMAT:
For each image, provide detailed analysis:
- What specifically is visible in the image
- Whether it matches livestock waste/fertilizer characteristics
- Color, texture, and form indicators
- Context clues (bags, containers, agricultural setting)

Return JSON:
{{
  "verdict": "VERIFIED_LEGITIMATE" or "VERIFIED_NOT_LEGITIMATE" or "UNABLE_TO_VERIFY",
  "confidence": 0.0-1.0,
  "reason": "Provide comprehensive explanation covering: 1. Detailed description of what is visible in the image(s), 2. Specific characteristics that indicate livestock waste/fertilizer or lack thereof, 3. Context clues from the setting or packaging, 4. Why the image meets the criteria for the verdict. Be thorough in your analysis.",
  "isLegitimateWaste": true/false,
  "wasteType": "manure|compost|fertilizer|organic_waste|not_applicable",
  "processingTime": "{time.time() - start_time:.2f}s"
}}

IMPORTANT: The reason field must be comprehensive and detailed, explaining ALL visual factors that led to the verdict. Be specific about what you see in the images."""
        
        # Call OpenAI
        print(" Calling OpenAI API with vision support for listing image validation...")
        print(f" Content items: {len(user_content)} (text: 1, images: {len(all_image_urls)})")
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                max_tokens=1000,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            ai_response = response.choices[0].message.content
            print(f" OpenAI Response received: {ai_response[:200]}...")
            
            validation_result = json.loads(ai_response)
            
            # Ensure required fields exist
            if not validation_result.get('verdict'):
                raise Exception("OpenAI response missing verdict field")
            
            # Validate verdict
            valid_verdicts = ['VERIFIED_LEGITIMATE', 'VERIFIED_NOT_LEGITIMATE', 'UNABLE_TO_VERIFY']
            if validation_result['verdict'] not in valid_verdicts:
                print(f" Invalid verdict from OpenAI: {validation_result['verdict']}, defaulting to UNABLE_TO_VERIFY")
                validation_result['verdict'] = 'UNABLE_TO_VERIFY'
            
            # Set isLegitimateWaste based on verdict
            validation_result['isLegitimateWaste'] = validation_result['verdict'] == 'VERIFIED_LEGITIMATE'
            
            # Ensure reason is clean
            if validation_result.get('reason'):
                validation_result['reason'] = validation_result['reason'].strip()
            
            print(f" FINAL RESULT: {json.dumps(validation_result, indent=2)}")
            
            return jsonify({
                "status": "success",
                "result": validation_result,
                "processing_time": f"{time.time() - start_time:.2f}s",
                "image_analyzed": len(all_image_urls) > 0,
                "images_analyzed": len(all_image_urls),
                "content_type": "listing_image"
            }), 200
        except Exception as openai_error:
            print(f" OpenAI API Error: {openai_error}")
            raise
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

@app.route('/', methods=['GET'])
def index():
    """Simple index route to confirm service status and list endpoints."""
    return jsonify({
        "service": "AgriLink AI Validation",
        "status": "running",
        "endpoints": [
            "/validate-report",
            "/validate-listing-report", 
            "/validate-listing-image",
            "/validate-comment-report",
            "/validate-message-report",
            "/generate-chat-suggestions",
            "/analyze-chat-transaction",
            "/check-chat-inactivity",
            "/health"
        ]
    }), 200

if __name__ == '__main__':
    print("Starting AgriLink AI Validation Server...")
    print("OpenAI API Key configured")
    print("AgriLink moderator rules loaded")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
