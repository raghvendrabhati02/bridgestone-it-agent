import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

def main():
    print("--- DIRECT GEMINI TEST ---")
    load_dotenv()
    
    # Load API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not defined in environment variables.")
        sys.exit(1)
        
    print(f"Loaded API key successfully. Prefix: {api_key[:6]}...")
    
    # Initialize SDK
    try:
        genai.configure(api_key=api_key)
        print("SDK configured successfully.")
    except Exception as e:
        print(f"Error configuring SDK: {e}")
        sys.exit(1)
        
    # Model selection
    model_name = "gemini-2.5-flash-lite"
    print(f"Selected model: {model_name}")
    
    # Simple prompt execution
    prompt = "Hello"
    print(f"Executing prompt: '{prompt}'...")
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            request_options={"timeout": 15.0}
        )
        print("\nResponse successfully received!")
        print(f"Model Name: {model_name}")
        print(f"Response Text: {response.text.strip()}")
    except Exception as e:
        print("\nError occurred during generate Content:")
        print(f"Type: {type(e)}")
        print(f"Message: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
