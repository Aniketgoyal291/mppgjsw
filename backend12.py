import os
import base64
import json
import requests
import pypdfium2 as pdfium
from PIL import Image
import io
from dotenv import load_dotenv
import pandas as pd
from gradio_client import Client
import tempfile

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
API_URL = "https://api.openai.com/v1/chat/completions"

# Full JSON schema for all parameters
FULL_SCHEMA = {
    "type": "object",
    "properties": {
        # Important features
        "cylinder_action":            {"type": "string"},
        "bore_diameter":              {"type": "string"},
        "outside_diameter":           {"type": "string"},
        "rod_diameter":               {"type": "string"},
        "stroke_length":              {"type": "string"},
        "close_length":               {"type": "string"},
        "operating_pressure":         {"type": "string"},
        "operating_temperature":      {"type": "string"},
        "mounting":                   {"type": "string"},
        "rod_end":                    {"type": "string"},
        "fluid":                      {"type": "string"},
        "drawing_number":             {"type": "string"},
        "revision":                   {"type": "string"}
    },

    "required": [
        "cylinder_action","bore_diameter","outside_diameter","rod_diameter",
        "stroke_length","close_length","operating_pressure",
        "operating_temperature","mounting","rod_end","fluid","drawing_number","revision"
    ]
}
                
'''# Optional features
        "body_material":              {"type": "string"},
        "piston_material":            {"type": "string"},
        "cylinder_configuration":     {"type": "string"},
        "cylinder_style":             {"type": "string"},
        "rated_load":                 {"type": "string"},
        "standard":                   {"type": "string"},
        "surface_finish":             {"type": "string"},
        "coating_thickness":          {"type": "string"},
        "special_features":           {"type": "string"},
        "concentricity_of_rod_and_tube": {"type": "string"}
        
       in required: "body_material","piston_material","cylinder_configuration","cylinder_style",
        "rated_load","standard","surface_finish","coating_thickness",
        "special_features","concentricity_of_rod_and_tube"'''
    



# Feature groups
IMPORTANT_FEATURES = [
    "cylinder_action", "bore_diameter", "outside_diameter",
    "rod_diameter", "stroke_length", "close_length",  # first 6
    "operating_pressure", "operating_temperature",
    "mounting", "rod_end", "fluid", "drawing_number", "revision"   # next 7
]

'''OPTIONAL_FEATURES = [
    "body_material", "piston_material", "cylinder_configuration",
    "cylinder_style", "rated_load", "standard", "surface_finish",
    "coating_thickness", "special_features", "concentricity_of_rod_and_tube"
]
'''
SYSTEM_CONTENT_ANALYSIS = (
    """You are an elite mechanical drawing interpreter with 50 years of experience as a hydraulic cylinder engineer. 
    Your expertise lies in analyzing technical drawings of hydraulic and pneumatic cylinders with unparalleled precision. 
    You can read between the lines, synthesize information from disparate parts of the drawing, and apply deep domain knowledge. 
    Your ultimate goal is to extract 100% accurate specifications and design values from these drawings. 
    If a value is not explicitly stated, you MUST use your extensive engineering knowledge, industry standards, 
    and the provided inference rules to determine the most probable and accurate value. 
    Only use 'NA' if a parameter is truly uninferable and meaningless in the context of a cylinder drawing, 
    after exhausting all inference possibilities and considering all typical engineering values."""
)
SYSTEM_CONTENT_VALIDATOR = (
    "You are a senior validation engineer specializing in hydraulic and pneumatic cylinder design verification. "
    "Your task is to meticulously cross-check all extracted parameters against the actual mechanical drawing image. "
    
    "Your validation process must include:\n"
    "1. **Presence Check**: For each parameter, determine if the value is explicitly visible or measurably derivable from the drawing. "
    "   - If a parameter is not present and no visual, textual, or dimensional evidence supports its existence, override the value with 'NA'. "
    "   - This ensures that no assumed or hallucinated values pass through the verification stage.\n"
    
    "2. **Exact Value Check**: If the parameter *is* present, validate the extracted value with pixel-level accuracy: "
    "   - Compare every digit, unit, and symbol against the image."
    "   - For measurements, verify against actual drawing dimensions (arrows, dimension lines, scales, callouts, etc.). "
    "   - Confirm labels such as 'BORE', 'ROD', or 'STROKE' via their proper association with the correct measurement.\n"
    
    "3. **Correction Logic**: For any discrepancy (wrong value, format, missing data, or misread unit), correct it precisely. "
    "   - Preserve original formatting, casing, and units as seen in the image (e.g., 'Ø50 mm', '250 BAR')."
    "   - Do not carry over any inferred values from the previous model unless they are verifiably correct from the image.\n"
    
    "4. **Output Schema**: Return a complete JSON with all parameters. "
    "   - If a value is confirmed, return it unchanged. "
    "   - If a value is incorrect or unsupported by the image, return the corrected value or 'NA'." \
    "  **JSON ONLY:** Your entire response MUST be a single, raw JSON object. Nothing else."
        "**NO EXTRA TEXT:** Do not include any introductory text, explanations, apologies, or closing remarks."
        "**NO MARKDOWN:** Do not wrap the JSON in markdown code blocks (like ```json ... ```), backticks, or any other formatting."
        "**SCHEMA MATCH:** The JSON object must strictly adhere to the provided JSON schema. All properties must be present."
        "**START AND END:** Your response must begin with the character `{` and end with the character `}`."
    
    "You are the final gatekeeper before these values are used for critical engineering decisions. Precision is paramount."
)

try:
    upscale_client = Client("https://bookbot-image-upscaling-playground.hf.space/")
    print("✅ Gradio upscale client initialized successfully.")
except Exception as e:
    print(f"⚠️ Warning: Could not initialize upscale client. Upscaling will be disabled. Error: {e}")
    upscale_client = None

# --- Utility functions ---

def encode_image_to_base64(image_bytes):
    return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode('utf-8')


def convert_pdf_to_image_bytes(pdf_bytes):
    """Converts the first page of a PDF to JPEG image bytes using pypdfium2."""
    try:
        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        page = pdf_doc[0]
        image_pil = page.render(scale=2).to_pil()

        if image_pil.mode == 'RGBA':
            image_pil = image_pil.convert('RGB')

        buf = io.BytesIO()
        image_pil.save(buf, format='JPEG', quality=95)
        pdf_doc.close()
        return buf.getvalue()
    except Exception as e:
        print(f"Error converting PDF with pypdfium2: {e}")
        return None


def get_rotation_suggestion_from_ai(image_bytes, filename="unknown"):
    """
    Uses GPT-4o to determine the necessary rotation for an engineering drawing.
    (This function remains unchanged, using gpt-4o and base64).
    """
    base64_image = encode_image_to_base64(image_bytes)
    
    system_prompt = (
        "You are an expert in image geometry and document layout analysis, specializing in engineering drawings. "
    "Your sole task is to determine the correct orientation of a scanned engineering drawing image so that"
    "all important text (especially the title block, part labels, and specification tables) is upright and readable from left to right in standard portrait orientation."
    "You will return your answer strictly in JSON format without any explanations or additional content."
)
    user_prompt_template = """
    Analyze the provided engineering drawing to determine the rotation needed to make its text content upright and readable.
    Your primary focus MUST be the main title block (the table containing drawing numbers, specifications, approvals, etc.) is upright and readable from left to right.

    **The single most important rule is to orient the image so the text inside the title block reads correctly from left-to-right.**
    The standard position for this block is at the bottom-right of the frame.

    Instructions:
    1.  **Identify the main title block.** This is the rectangular grid with the most important metadata.
    2.  **Determine the rotation** that makes the text *within that block* horizontal and readable.
    3.  **Ignore other text** if it conflicts with the title block's orientation. Text along the page edges is often misleading.
    4.  The final aspect ratio (portrait or landscape) does not matter; only the readability of the main content matters.

    Decide how much counter-clockwise rotation (in degrees) is needed to correct the image.
    Rotation must be one of: 0, 90, 180, 270.
    Definitions:
    - Use 0 if the title block text is already upright.
    - Use 90 if the top of the title block is currently on the right (requires 90° CCW rotation).
    - Use 180 if the title block is upside down.
    - Use 270 if the top of the title block is currently on the left (requires 270° CCW rotation).

    You MUST respond ONLY with a JSON object that adheres to the following schema.
    Do not include any other text, explanations, or markdown.

    JSON SCHEMA:
    {{
      "type": "object",
      "properties": {{
        "rotation_angle_ccw": {{
          "type": "integer",
          "description": "The required counter-clockwise rotation in degrees. Must be 0, 90, 180, or 270."
        }},
        "reasoning": {{
          "type": "string",
          "description": "A brief explanation for your choice."
        }}
      }},
      "required": ["rotation_angle_ccw", "reasoning"]
    }}
    """

    payload = {
        "model": "gpt-4o", 
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_template},
                    {"type": "image_url", "image_url": {"url": base64_image, "detail": "high"}}
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }
    local_headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}", 
        "Content-Type": "application/json"
    }
    try:
        print(f"-> AI checking orientation for {filename}...")
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=local_headers, json=payload, timeout=30)
        response.raise_for_status()
        
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        
        angle = data.get("rotation_angle_ccw", 0)
        if angle in [0, 90, 180, 270]:
            print(f"-> AI suggests {angle}° rotation. Reason: {data.get('reasoning', 'N/A')}")
            return angle
        else:
            print(f"-> AI returned an invalid angle: {angle}. Defaulting to 0.")
            return 0
    except Exception as e:
        print(f"-> Error during AI orientation check for {filename}: {e}. Defaulting to no rotation.")
        return 0


def rotate_image(image_bytes, angle_ccw):
    if angle_ccw == 0:
        return image_bytes
    try:
        image = Image.open(io.BytesIO(image_bytes))
        rotated_image = image.rotate(angle_ccw, expand=True)
        output_buffer = io.BytesIO()
        img_format = image.format if image.format and image.format != 'MPO' else 'JPEG'
        if img_format.upper() == 'PNG':
            rotated_image.save(output_buffer, format='PNG')
        else:
            if rotated_image.mode in ('RGBA', 'P'):
                rotated_image = rotated_image.convert('RGB')
            rotated_image.save(output_buffer, format='JPEG', quality=95)
        print(f"-> Image successfully rotated by {angle_ccw} degrees.")
        return output_buffer.getvalue()
    except Exception as e:
        print(f"-> Error during image rotation: {e}. Returning original image.")
        return image_bytes


def try_upscale(image_bytes):
    if not upscale_client:
        print("-> Upscaling client not available. Skipping.")
        return image_bytes
    
    temp_input_path = None
    temp_output_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_bytes)
            temp_input_path = tmp.name
        print("-> Upscaling image...")
        temp_output_path = upscale_client.predict(temp_input_path, "modelx2", api_name="/predict")
        with open(temp_output_path, "rb") as f_up:
            upscaled_bytes = f_up.read()
        print("-> Upscaling successful.")
        return upscaled_bytes
    except Exception as e:
        print(f"-> Warning: Upscaling failed: {e}. Using original image.")
        return image_bytes
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            os.remove(temp_input_path)
        if temp_output_path and os.path.exists(temp_output_path):
            os.remove(temp_output_path)


# --- NEW: Image Upload Function ---
def upload_to_imgbb(image_bytes):
    """Uploads image bytes to imgbb and returns the public URL."""
    if not IMGBB_API_KEY:
        print("-> Error: IMGBB_API_KEY is not set. Cannot upload image.")
        return None
    
    print("-> Uploading image to ImgBB for analysis...")
    try:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": image_bytes}
        )
        response.raise_for_status()
        data = response.json()
        if data.get("success"):
            image_url = data["data"]["url"]
            print(f"-> ImgBB upload successful: {image_url}")
            return image_url
        else:
            print(f"-> ImgBB upload failed. Response: {data}")
            return None
    except Exception as e:
        print(f"-> Error during ImgBB upload: {e}")
        return None



def extract_feature_batch(image_url, features, filename, batch_name):
    """MODIFIED: Accepts an image_url and uses o4 mini model."""
    local_headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    minimal_schema = {
    "type": "object",
    "properties": {
        k: FULL_SCHEMA["properties"][k] for k in features
    } | {
        "close_length_reasoning": {
            "type": "string",
            "description": "Step-by-step reasoning and justification for the extracted close length value. Mention what values were used, whether it was explicitly found or inferred, and how."
        }
    },
    "required": features + ["close_length_reasoning"]
}
    user_msg = (
        f'''YOU MUST EXTRACT 100% OF ALL PARAMETERS DEFINED IN THE JSON SCHEMA BELOW — NO EXCEPTIONS.

ABSOLUTE EXTRACTION RULES:
1. Extract all parameters exactly as defined in the JSON schema.
2. Use explicit values found in the drawing whenever available.
3. If a value is not explicitly stated, apply your 50 years of hydraulic/pneumatic cylinder engineering expertise and the inference rules below to determine the most accurate value.
4. Only use "NA" if a parameter is truly uninferable and meaningless in this context.
5. Accept parameter names with ≥90% similarity to schema names (see equivalences below).

PARAMETER NAME EQUIVALENCES (≥90% match):
- "BORE:", "ID:" → "BORE DIAMETER"
- "OD:", "OUTER DIA:" → "OUTSIDE DIAMETER"
- "ROD:", "RD:" → "ROD DIAMETER"
- "STROKE:", "S.L." → "STROKE LENGTH"
- "CLOSE:" → "CLOSE LENGTH"
- "PRESSURE:" → "OPERATING PRESSURE"
- "TEMP:" → "OPERATING TEMPERATURE"
- "DWG NO:", "DRG NO:", "PART NO:" → "DRAWING NUMBER"
- "REV", "Revision" → "REVISION"
- "FLUID:", "MEDIUM:" → "FLUID"
- "MOUNTING:" → "MOUNTING"
- "ACTION:" → "CYLINDER ACTION"

CRITICAL PARAMETERS TO EXTRACT (AND INFER IF NECESSARY):
- BORE DIAMETER: (Look for **BORE** labeled with "CYLINDER BORE", "BORE:", or the diameter symbol "Ø" near the barrel of the cylinder.
    The **bore diameter** refers to the inner diameter of the cylinder tube.
    If the bore diameter is not labeled, infer it by checking the piston diameter or the tube's outer diameter (OD) and using wall thickness (if available).
    Typically, the bore will be shown close to the barrel in cross-section views of the cylinder.)
- OUTSIDE DIAMETER: (Look for labels such as "OD:", "OUTER DIA:", or any direct mention of the outside diameter near the outer section of the cylinder.
    If the outside diameter is not explicitly provided, infer it based on the bore diameter and a typical wall thickness. 
    In cases where additional clearance is specified, factor that into the estimation.
    Strictly Focus on the cross-sectional view of the cylinder. In this view, the bore will be visible as the inner part it might not be labelled but it will be there. The outer circle/box (if square then its side is the diameter) represents the total outside diameter of the cylinder. 
    The outside diameter is simply the diameter/length of the outer or total part in the cross-section view.)
- STROKE LENGTH: (Search for **STROKE** labeled with "STROKE LENGTH", "STROKE:", or abbreviations like "S.L."
    Stroke length is the distance the piston moves inside the cylinder from its fully retracted position to its fully extended position.
    If stroke length is not explicitly mentioned, compute it from the **OPEN LENGTH** and **CLOSE LENGTH**.
    Look for annotations related to the **piston travel range** or **stroke markings** in the technical sections or dimensions of the cylinder.)
    also provide the resoning by which you calculated the close length parameter in the reasoning field in the json.
- CLOSE LENGTH: (Look for labels such as CLOSE LENGTH, RETRACTED LENGTH, or MINIMUM LENGTH. 
    In the image, CLOSE LENGTH is calculated by subtracting the **STROKE LENGTH** from the EXTENDED LENGTH.
    The closed length is measured from the centerline of the mounting points at each end of the cylinder, to the end of the cylinder in the retracted position, where the piston rod is fully inside the cylinder..
    CLOSE LENGTH is often mentioned near the cylinder retraction description or in the context of piston movement.)
    Additionally, you must provide a "close_length_reasoning" field in the output JSON. This should contain a step-by-step explanation of how the "close_length" value was extracted or inferred. If it was directly labeled, mention the label. If it was calculated (e.g., from stroke + open length), show the formula. Always explain the logic clearly — do not guess silently.
- ROD DIAMETER: (Look for **ROD DIAMETER**, **ROD**, or "Ø" symbols near the **piston rod** section of the cylinder.
    The **ROD DIAMETER** is the diameter of the piston rod, and in the drawing, it is clearly marked near the rod area.
    If not explicitly mentioned, look for **dimensions near the rod section** of the cylinder and check if there are any cross-sectional views showing the rod's size.)
- OPERATING PRESSURE: (Look for labels such as PRESSURE, WORKING PRESSURE, or similar terms. Check for units like BAR, MPa, or any pressure-related indications in the drawing.
    The OPERATING PRESSURE is usually found in the technical specification section or near pressure-related diagrams. 
    If it's missing, infer it based on related symbols or contextual information, such as pressure valve annotations.)
- OPERATING TEMPERATURE: (Look for labels like TEMP, TEMPERATURE, or any closely related terms in the drawing. This value typically appears in the technical specification section.
    If the temperature is not explicitly mentioned, look for system specifications or operational limits that could suggest the temperature range. 
    You can also infer it based on the type of fluid used or the working conditions described in the drawing.)
- DRAWING NUMBER: (Search for labels such as DWG NO, DRG NO, PART NO, or any similar identifier.
    The DRAWING NUMBER is typically located at the right bottom section of the image in the title block or near the technical specifications.)
- REVISION: (Look for "REV", "Revision" or any mentioned with any close name, often located near the drawing number or part number. 
    The revision number will typically be a two-digit value (e.g., 00, 01, 02, 03).
    If found, return the revision value; if no revision number is present, return "00" in json as value if it is missing.)
- FLUID: Look for "FLUID:", "OIL:", "AIR:".(read the FLUID HANDLING RULES)
- MOUNTING: (Identify the mounting type either by visual clues or text labels like CLEVIS, FLANGE, LUG, TRUNNION, or ROD EYE.
    Mounting types are typically indicated in the technical specification section or near the cylinder's visual diagram.
    If not explicitly labeled,check VISUAL INFERENCE GUIDELINES so that you will be able to analyse by observing the diagram.)
- ROD END: (Look for labels such as ROD END, THREAD, CLEVIS, or ROD EYE.
    These terms define the type of attachment or connection at the end of the piston rod. 
    If no label is found, look for visual clues showing the type of connection, such as thread types or clevis fittings in the diagram.)
- CYLINDER ACTION: (Infer the cylinder action based on the number of ports or the cylinder type. A double-acting cylinder typically has 2 ports, while a single-acting cylinder has only 1 port.
    Infer the cylinder action by looking for acting-related terms such as **"DOUBLE ACTING"** or **"SINGLE ACTING"** in the text area of the drawing)
EXTRACTION STRATEGY:
- First, extract from specification/dimension tables (highest priority).
- Then parse callouts, arrows, labeled dimensions near drawing features and find values from the drawing.
- Examine the corners for drawing number mostly it will be in bottom right corner section but if not here then look for other corners.
- Check notes or remarks for pressure, temperature, special features.
- Use geometric shape recognition for mounting and rod end types.
- Employ OCR reasoning to read faint or rotated text.
- Respect units as given; do not convert unless instructed.
- Avoid estimating values by scaling the drawing.
- Use your deep domain expertise and inference rules to fill gaps logically.

VISUAL INFERENCE GUIDELINES:
- CLEVIS: A clevis mount appears as a forked U-shaped structure typically located at the rear (cap end) of the cylinder. It has two parallel arms with a transverse hole through both for a pin, allowing the cylinder to pivot during operation. This configuration is commonly used in applications where rotational freedom is required. Visually, look for symmetrical fork arms extending from the cylinder and a clearly defined central hole aligned across the arms.
- FLANGE: A flange mount is identified by a flat disc or rectangular plate extending from the front or rear of the cylinder, featuring multiple evenly spaced bolt holes around its perimeter. This type of mount is used for rigid, fixed installations where no rotation is needed. In drawings, it appears as a flush face plate directly attached to the end cap, often with visible bolt circle markings or dimensioned bolt patterns.
- LUG: A flange mount is identified by a flat disc or rectangular plate extending from the front or rear of the cylinder, featuring multiple evenly spaced bolt holes around its perimeter. This type of mount is used for rigid, fixed installations where no rotation is needed. In drawings, it appears as a flush face plate directly attached to the end cap, often with visible bolt circle markings or dimensioned bolt patterns.
- TRUNNION: A trunnion mount features a cylindrical pivot pin or axle that extends horizontally from the center or ends of the cylinder barrel. This design enables pivoting around the trunnion axis and is ideal for applications where the cylinder must follow an arc or swing. Look for a smooth cylindrical shaft centered and perpendicular to the cylinder body, either mid-barrel or attached to the heads.
- ROD END CLEVIS: A clevis on the rod end is a small U-shaped fork with a pinhole, used to attach the rod to a mating component. This allows angular freedom at the connection point. Visually, it mirrors the clevis mounting style but is located at the tip of the piston rod. It typically has two short arms extending from the rod with a central hole that accommodates a pivot pin.
- ROD END THREAD: A threaded rod end is seen as a straight cylindrical shaft with visible threads (male) or a recessed threaded hole (female). This allows for secure mechanical fastening into a mating part. In drawings, look for parallel ridges or note callouts indicating thread specifications such as "M20x1.5" or internal threading with depth markings.
- ROD END ROD EYE: The rod eye is a looped end with a centered hole, often used with a spherical bearing or bushing to allow for misalignment and multidirectional articulation. It appears as a circular eyelet at the rod's tip, and may contain additional details like a bearing symbol or internal ring. This design provides robust connection while accommodating slight angular movement.

FLUID HANDLING RULES (STRICT):
- If "Mineral Oil" is mentioned, return **HYD. OIL MINERAL**.
- If "HLP68", "ISO VG46", or "Synthetic Oil" are mentioned, keep the term as it is.
- If "Compressed Air", "Pneumatic", or "AIR" is mentioned, return **FLUID = AIR**.
- If fluid is not directly specified but the drawing indicates a **hydraulic cylinder** (e.g., high pressure, robust construction), infer **HYD. OIL MINERAL**.
- If the system is **pneumatic** (indicated by words like pneumatic or compressed air), infer **FLUID = AIR**.

Pay particular attention to words like **hydraulic** or **pneumatic** within the drawing, as these terms will be a key indicator of the type of fluid, even if the word "fluid" is not directly mentioned.

OUTPUT REQUIREMENTS:
- Respond only with a JSON object exactly matching the provided JSON schema.
- Include all schema properties with values, inferred if necessary.
- Avoid printing complex special characters (e.g., Omega (Ω), diameter (⌀)), but if simple symbols like plus (+), minus (−), or degree (°) appear, they are allowed. If any complex symbol is present, exclude the symbol and just take the number or text around it without using the symbol.
- Use "NA" for uninferable values.
- No additional text, explanations, or markdown outside the JSON.
- The final output must be a valid JSON object that includes all required fields, plus a `close_length_reasoning` string with the detailed reasoning behind the close_length extraction.


JSON SCHEMA:
{json.dumps(minimal_schema, indent=2)}

NOW ANALYZE THIS CYLINDER DRAWING AND EXTRACT ALL PARAMETERS INTO THE JSON OBJECT, APPLYING INFERENCE RULES AS NEEDED.
        ''' 
    )
    payload = {
        #"model": "gpt-4o-mini", 
        "model": "o4-mini-2025-04-16", # CHANGED to reasoning model
        # "reasoning": {"effort": "high"},
        "messages": [
            {"role": "system", "content": SYSTEM_CONTENT_ANALYSIS},
            {"role": "user", "content": [
                {"type": "text", "text": user_msg},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
            ]}
        ],
        #"max_tokens": 1500,
        # "temperature": 0,
        #"response_format": {"type": "json_object"}
    }
    print(f"-> Analyzing {batch_name} for '{filename}'...")
    print(payload)
    resp = requests.post(API_URL, headers=local_headers, json=payload)
    print(resp.json())
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return content


def validate_feature_batch(image_url, extracted, filename, batch_name):
    """MODIFIED: Accepts an image_url and uses o4 mini model."""
    local_headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    user_msg = (
    "Please validate the following extracted parameters against the attached cylinder drawing image."
    "Validation Instructions:"
    "- If a value is clearly present in the image (via dimension lines, text, or callouts), verify it character-by-character."
    "- If the value is missing, partially visible, or unverifiable, replace it with 'NA'."
    "- Correct any mismatch or format issues using only the drawing as a source."
    "**Output Format:**"
    "Return the full corrected JSON with validated parameters, following the same structure:"
    "SPECIAL INSTRUCTIONS: RETURN ONLY VALIDATED JSON OBJECT NOTHING ELSE NO WORDS NOTHING JUST JSON OBJECT Start directly { <parameters>:<value> } Nothing else "
    + json.dumps(extracted, indent=2)
    )
    payload = {
        "model": "o4-mini-2025-04-16", 
        "messages": [
            {"role": "system", "content": SYSTEM_CONTENT_VALIDATOR},
            {"role": "user", "content": [
                {"type": "text", "text": user_msg},
                {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
            ]}
        ],
        # #"max_tokens": 1500,
        # "temperature": 0,
       # "response_format": {"type": "json_object"}
    }
    print(f"-> Validating {batch_name} for '{filename}'...")
    resp = requests.post(API_URL, headers=local_headers, json=payload)
    print("\n\n\n\n\n\n\n\n\n\n\n")
    print(resp.json(),"validation")
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    if isinstance(content, str):
        content = json.loads(content)
    return content


def process_single_file(file_bytes, filename="uploaded_file"):
    """
    Accepts raw bytes, runs the full pipeline, and YIELDS status updates.
    MODIFIED to upload the image to ImgBB once and reuse the URL.
    """
    try:
        # --- Stage 1: Pre-processing (Unchanged) ---
        yield {"status": "Preparing file...", "progress": 0.05}
        if file_bytes[:4] == b'%PDF':
            yield {"status": "Converting PDF to image...", "progress": 0.1}
            image = convert_pdf_to_image_bytes(file_bytes)
            if not image:
                yield {"error": "Failed to convert PDF to image."}
                return
        else:
            image = file_bytes
        
        '''if upscale_client:
            yield {"status": "Upscaling image for better clarity...", "progress": 0.15}
            image = try_upscale(image)'''

        yield {"status": "AI (GPT-4o) is checking orientation...", "progress": 0.25}
        angle = get_rotation_suggestion_from_ai(image, filename)
        if angle != 0:
            yield {"status": f"Rotating image by {angle} degrees...", "progress": 0.30}
            image = rotate_image(image, angle)

        # --- NEW Stage: Upload to ImgBB ---
        yield {"status": "Uploading image for analysis...", "progress": 0.35}
        image_url = upload_to_imgbb(image)
        if not image_url:
            yield {"error": "Failed to upload image to hosting service. Cannot proceed."}
            return

        results = {}
        
        # --- Stage 2: Batch 1 (Core Parameters) ---
        yield {"status": "Analyzing core parameters (Batch 1/2)...", "progress": 0.4}
        ext1 = extract_feature_batch(image_url, IMPORTANT_FEATURES[:6], filename, 'batch1')
        yield {"status": "Validating core parameters (Batch 1/2)...", "progress": 0.5}
        # val1 = validate_feature_batch(image_url, ext1, filename, 'batch1')
        results.update(ext1)

        # --- Stage 3: Batch 2 (Secondary Parameters) ---
        yield {"status": "Analyzing secondary parameters (Batch 2/2)...", "progress": 0.6}
        ext2 = extract_feature_batch(image_url, IMPORTANT_FEATURES[6:], filename, 'batch2')
        yield {"status": "Validating secondary parameters (Batch 2/2)...", "progress": 0.8}
        # val2 = validate_feature_batch(image_url, ext2, filename, 'batch2')
        results.update(ext2)

        # --- Stage 4: Batch 3 (Optional Parameters) ---
        #yield {"status": "Analyzing optional parameters (Batch 3/3)...", "progress": 0.9}
        #ext3 = extract_feature_batch(image_url, OPTIONAL_FEATURES, filename, 'batch3')
        #results.update(ext3)
        #yield {"status": "Validating optional parameters (Batch 3/3)...", "progress": 0.9}
        #val3 = validate_feature_batch(image_url, ext3, filename, 'batch3')
        #results.update(val3)
        
        yield {"status": "Finalizing results...", "progress": 0.9}

        # --- Final Stage: Yield the result ---
        yield {
            "final_result": {
                "data": results,
                # The final image bytes are still available if needed by the frontend
                "image": image 
            },
            "progress": 1.0
        }

    except Exception as e:
        yield {"error": f"An unexpected error occurred in the backend: {str(e)}"}


# --- Main entrypoint ---

def main():
    pdf_dir = r"C:\Users\Omkar\Desktop\Final_code_with_98%_accuracy\data"
    pdf_files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    
    all_data = []
    for pdf_path in pdf_files:
        try:
            print(f"→ Processing {os.path.basename(pdf_path)}")
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            final_result = None
            # The process_single_file is a generator, so we must iterate through it
            for update in process_single_file(pdf_bytes, filename=os.path.basename(pdf_path)):
                if "error" in update:
                    print(f"ERROR: {update['error']}")
                    final_result = {"filename": os.path.basename(pdf_path), "data": {"error": update['error']}}
                    break
                elif "final_result" in update:
                    # We only care about the final result for this main script
                    record_data = update['final_result']['data']
                    final_result = {"filename": os.path.basename(pdf_path), "data": record_data}
                    break # Exit the loop once we have the final result
                else:
                    # Print progress updates to the console
                    print(f"  [{int(update['progress']*100)}%] {update['status']}")
            
            if final_result:
                all_data.append(final_result)

        except Exception as exc:
            record = {"filename": os.path.basename(pdf_path), "data": {"error": str(exc)}}
            all_data.append(record)

    # Save JSON
    with open('extracted_data.json', 'w') as outf:
        json.dump(all_data, outf, indent=2)
    # Save Excel
    df = pd.DataFrame([{'filename': r['filename'], **r['data']} for r in all_data])
    df.to_excel('extracted_data.xlsx', index=False)
    print(" Done: Data saved to JSON and Excel.")

if __name__ == '__main__':
    main()