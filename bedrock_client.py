import boto3
import re
import unicodedata
import time
from botocore.exceptions import ClientError, ReadTimeoutError
from botocore.config import Config

# Initialize Bedrock runtime client with timeout
config = Config(
    connect_timeout=5,
    read_timeout=30
)
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1', config=config)

def sanitize_input(text):
    """
    Sanitize user input to prevent prompt injection attacks and validate input quality
    
    Args:
        text (str): User input to sanitize
    
    Returns:
        str: Sanitized input
    
    Raises:
        ValueError: If injection patterns, gibberish, or fraudulent claims are detected
    """
    # Normalize unicode input
    text = unicodedata.normalize('NFKC', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Cap input length at 2000 characters
    if len(text) > 2000:
        text = text[:2000]
    
    # Check for gibberish: at least 5 real words (alphabetic tokens of 3+ characters)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    if len(words) < 5:
        raise ValueError('Input does not appear to be a valid financial offer. Please provide real offer terms.')
    
    # Detect absurd/fraudulent offer patterns
    fraudulent_patterns = [
        r'1000%',
        r'100%\s*cashback',
        r'free\s+money',
        r'guaranteed\s+approval',
        r'no\s+payments?\s+ever',
        r'unlimited\s+credit',
        r'no\s+interest\s+ever',
        r'no\s+terms',
        r'no\s+conditions'
    ]
    
    # Check for fraudulent patterns (case insensitive)
    text_lower = text.lower()
    for pattern in fraudulent_patterns:
        if re.search(pattern, text_lower):
            raise ValueError('Input contains unrealistic or potentially fraudulent claims. Please describe a legitimate offer.')
    
    # Detect prompt injection patterns
    injection_patterns = [
        r'ignore previous instructions',
        r'you are now',
        r'disregard your',
        r'new instruction:',
        r'system:',
        r'forget everything',
        r'act as',
        r'pretend to be',
        r'roleplay',
        r'override',
        r'bypass',
        r'circumvent',
        r'ignore system'
    ]
    
    # Check for injection patterns (case insensitive)
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            raise ValueError('Invalid input detected')
    
    return text

def log_call(model_id, input_length, response_length):
    """Safely log call details without sensitive data"""
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Model: {model_id} - Input: {input_length} chars - Response: {response_length} chars")

def check_rate_limit():
    """Check rate limit (10 calls per minute)"""
    import streamlit as st
    
    if 'call_timestamps' not in st.session_state:
        st.session_state.call_timestamps = []
    
    current_time = time.time()
    # Remove timestamps older than 60 seconds
    st.session_state.call_timestamps = [ts for ts in st.session_state.call_timestamps if current_time - ts < 60]
    
    if len(st.session_state.call_timestamps) >= 10:
        raise ValueError('Too many requests. Please wait a moment before generating again.')
    
    st.session_state.call_timestamps.append(current_time)

def call_nova(system_prompt, user_message, model_id="amazon.nova-lite-v1:0"):
    """
    Call Amazon Nova model via AWS Bedrock
    
    Args:
        system_prompt (str): System prompt for the model
        user_message (str): User message to send
        model_id (str): Model ID to use (default: amazon.nova-lite-v1:0)
    
    Returns:
        str: Model response text
    
    Raises:
        RuntimeError: If call limit exceeded
        ClientError: If Bedrock API call fails
    """
    try:
        # Check rate limit
        check_rate_limit()
        
        # Prepare the request
        request = {
            "modelId": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": user_message
                        }
                    ]
                }
            ],
            "system": [
                {
                    "text": system_prompt
                }
            ],
            "inferenceConfig": {
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9
            }
        }
        
        # Make the API call
        response = bedrock_client.converse(**request)
        
        # Validate response structure
        if ("output" not in response or 
            "message" not in response["output"] or 
            "content" not in response["output"]["message"] or 
            len(response["output"]["message"]["content"]) == 0 or
            "text" not in response["output"]["message"]["content"][0]):
            raise RuntimeError('Unexpected response from Nova. Please try again.')
        
        # Extract response text
        response_text = response["output"]["message"]["content"][0]["text"]
        
        # Log call details safely
        log_call(model_id, len(user_message), len(response_text))
        
        return response_text
        
    except ReadTimeoutError:
        raise Exception('Request timed out. Please try again.')
    except ClientError as e:
        raise ClientError(f"Bedrock API error: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error calling Nova: {e}")
