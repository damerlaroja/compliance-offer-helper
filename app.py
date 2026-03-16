import streamlit as st
from botocore.exceptions import ClientError
from bedrock_client import call_nova, sanitize_input
from prompts import DRAFTER_SYSTEM, REVIEWER_SYSTEM

# Initialize session state for call counter
if 'call_count' not in st.session_state:
    st.session_state.call_count = 0

def clean_response(text):
    """Remove markdown strikethrough formatting from Nova response"""
    import re
    # Remove strikethrough formatting (~~text~~)
    return re.sub(r'~~(.*?)~~', r'\1', text)

def sanitize_output(text):
    """Remove potentially dangerous content from Nova responses"""
    import re
    # Remove HTML tags
    text = re.sub(r'<script.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<iframe.*?</iframe>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<a[^>]*href[^>]*>.*?</a>', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove javascript: URLs
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    return text

# Page configuration
st.set_page_config(
    page_title="Compliance Offer Helper",
    page_icon="🛡️",
    layout="wide"
)

# Main title and header
st.title("Compliance-Friendly Offer Helper")
st.subheader("Powered by Amazon Nova on AWS Bedrock")

# Sidebar
with st.sidebar:
    st.markdown("### About This App")
    st.markdown("""
    This app helps you create compliance-friendly customer messages for financial and commerce offers using AI.
    
    **How it works:**
    - **Drafter agent**: Creates customer-facing messages with clear terms
    - **Reviewer agent**: Checks compliance and provides feedback
    
    Built for Amazon Nova AI Hackathon 2026
    """)
    
    # Display call counter
    st.sidebar.metric('API Calls Used', f'{st.session_state.call_count}/200')

# Main content
col1, col2 = st.columns([1, 2])

with col1:
    # Input section
    st.markdown("### Offer Details")
    
    offer_type = st.selectbox(
        "Offer Type",
        options=["Credit card", "BNPL", "Installment loan"]
    )
    
    offer_desc = st.text_area(
        "Describe your offer terms",
        height=200,
        placeholder="e.g. 0% APR for 6 months on purchases over $500, then 24.99% variable APR. Late fee $35. No annual fee."
    )
    
    generate_btn = st.button("Generate Compliant Message", type="primary")

with col2:
    # Results section
    if generate_btn:
        if not offer_desc.strip():
            st.error("Please enter offer description")
        else:
            try:
                # Sanitize user input
                sanitized_desc = sanitize_input(offer_desc)
                
                # Check call limit
                if st.session_state.call_count >= 200:
                    st.error("API limit exceeded. Maximum 200 calls allowed.")
                else:
                    with st.spinner("Generating compliant message..."):
                        # Increment call counter
                        st.session_state.call_count += 1
                        
                        # Step 1: Generate draft
                        draft_input = f"Offer type: {offer_type}\n\n{sanitized_desc}"
                        draft = call_nova(DRAFTER_SYSTEM, draft_input)
                        
                        # Display draft (cleaned and sanitized)
                        st.markdown("### 📝 Drafted Message")
                        st.info(sanitize_output(clean_response(draft)))
                        
                        # Step 2: Review draft
                        with st.spinner("Reviewing for compliance..."):
                            # Increment call counter for review
                            st.session_state.call_count += 1
                            
                            review_input = f"Offer type: {offer_type}\n\nOriginal offer:\n{sanitized_desc}\n\nDrafted message:\n{draft}"
                            review = call_nova(REVIEWER_SYSTEM, review_input)
                            
                            # Parse verdict
                            if "VERDICT: OK" in review:
                                st.success("✅ Verdict: OK")
                            else:
                                st.warning("⚠️ Verdict: Needs Review")
                            
                            # Display full review (cleaned and sanitized)
                            st.markdown("### 🔍 Compliance Review")
                            st.markdown(sanitize_output(clean_response(review)))
                        
            except ValueError as e:
                if 'Invalid input detected' in str(e):
                    st.error('⚠️ Invalid input detected. Please describe a legitimate financial offer.')
                elif 'Input does not appear to be a valid financial offer' in str(e):
                    st.error('⚠️ Input does not appear to be a valid financial offer. Please provide real offer terms.')
                elif 'Input contains unrealistic or potentially fraudulent claims' in str(e):
                    st.error('⚠️ Input contains unrealistic or potentially fraudulent claims. Please describe a legitimate offer.')
                elif 'Too many requests' in str(e):
                    st.error('⚠️ Too many requests. Please wait a moment before generating again.')
                else:
                    st.error(f'⚠️ {str(e)}')
            except RuntimeError as e:
                if 'Unexpected response from Nova' in str(e):
                    st.error('⚠️ Unexpected response from Nova. Please try again.')
                else:
                    st.error(f"API error: {str(e)}")
            except Exception as e:
                if 'Request timed out' in str(e):
                    st.error('⚠️ Request timed out. Please try again.')
                else:
                    st.error(f"An unexpected error occurred: {str(e)}")

# Footer
st.markdown("---")
st.markdown("*Built with Amazon Nova AI on AWS Bedrock*")
