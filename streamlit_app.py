import streamlit as st
import pandas as pd
import json
from datetime import datetime
from scraper import fetch_html_selenium, save_raw_data, format_data, save_formatted_data, html_to_markdown_with_readability, scrape_url
from pagination_detector import detect_pagination_elements, PaginationData
import re
from urllib.parse import urlparse
import os


# Initialize Streamlit app
st.set_page_config(page_title=" Web Scraper", page_icon="🕸")
st.title(" Web Scraper ")

# Initialize session state variables if they don't exist
if 'results' not in st.session_state:
    st.session_state['results'] = None
if 'perform_scrape' not in st.session_state:
    st.session_state['perform_scrape'] = False

# Sidebar components
st.sidebar.title("Web Scraper Settings")
url_input = st.sidebar.text_input("Enter URL(s) separated by whitespace")

# Add toggle to show/hide tags field
show_tags = st.sidebar.toggle("Enable Scraping")

fields = ["Name", "Title", "Sport", "Email"]


st.sidebar.markdown("---")
# Add pagination toggle and input
use_pagination = st.sidebar.toggle("Enable Pagination")
pagination_details = None
if use_pagination:
    pagination_details = st.sidebar.text_input("Enter Pagination Details (optional)", 
        help="Describe how to navigate through pages (e.g., 'Next' button class, URL pattern)")

st.sidebar.markdown("---")


def generate_unique_folder_name(url):
    timestamp = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    
    # Parse the URL
    parsed_url = urlparse(url)
    
    # Extract the domain name
    domain = parsed_url.netloc or parsed_url.path.split('/')[0]
    
    # Remove 'www.' if present
    domain = re.sub(r'^www\.', '', domain)
    
    # Remove any non-alphanumeric characters and replace with underscores
    clean_domain = re.sub(r'\W+', '_', domain)
    
    return f"{clean_domain}_{timestamp}"

def scrape_multiple_urls(urls, fields):
    output_folder = os.path.join('output', generate_unique_folder_name(urls[0]))
    os.makedirs(output_folder, exist_ok=True)
    
    all_data = []
    first_url_markdown = None
    
    for i, url in enumerate(urls, start=1):
        raw_html = fetch_html_selenium(url)
        markdown = html_to_markdown_with_readability(raw_html)
        if i == 1:
            first_url_markdown = markdown
        
        formatted_data = scrape_url(url, fields, output_folder, i, markdown)
        all_data.append(formatted_data)
    
    return output_folder, all_data, first_url_markdown

# Define the scraping function
def perform_scrape():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    raw_html = fetch_html_selenium(url_input)
    markdown = html_to_markdown_with_readability(raw_html)
    save_raw_data(markdown, timestamp)
    
    # Detect pagination if enabled
    pagination_info = None
    if use_pagination:
        pagination_data = detect_pagination_elements(
            url_input, pagination_details, markdown
        )
        pagination_info = {
            "page_urls": pagination_data.page_urls
            
        }
    

    
    if show_tags:
    
        formatted_data = format_data(
            markdown,fields
        )
        df = save_formatted_data(formatted_data, timestamp)
    else:
        formatted_data = None
        df = None

    return df, formatted_data, markdown, timestamp, pagination_info

if st.sidebar.button("Scrape"):
    with st.spinner('Please wait... Data is being scraped.'):
        urls = url_input.split()
        field_list = fields
        output_folder, all_data, first_url_markdown = scrape_multiple_urls(urls, field_list)
        
        # Perform pagination if enabled and only one URL is provided
        pagination_info = None
        if use_pagination and len(urls) == 1:
            try:
                pagination_result = detect_pagination_elements(
                    urls[0], pagination_details, first_url_markdown
                )
                
                if pagination_result is not None:
                    pagination_data = pagination_result
                    
                    # Handle both PaginationData objects and dictionaries
                    if isinstance(pagination_data, PaginationData):
                        page_urls = pagination_data.page_urls
                    elif isinstance(pagination_data, dict):
                        page_urls = pagination_data.get("page_urls", [])
                    else:
                        page_urls = []
                    
                    pagination_info = {
                        "page_urls": page_urls
                    }
                else:
                    st.warning("Pagination detection returned None. No pagination information available.")
            except Exception as e:
                st.error(f"An error occurred during pagination detection: {e}")
                pagination_info = {
                    "page_urls": [],
                    
                }
        
        st.session_state['results'] = (all_data, None, first_url_markdown, output_folder, pagination_info)
        st.session_state['perform_scrape'] = True

# Display results if they exist in session state
if st.session_state['results']:
    all_data, _, _,  output_folder, pagination_info = st.session_state['results']
    
    # Display scraping details in sidebar only if scraping was performed and the toggle is on
    if all_data and show_tags:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Scraping Details")

        # Display scraped data in main area
        st.subheader("Scraped/Parsed Data")
        for i, data in enumerate(all_data, start=1):
            st.write(f"Data from URL {i}:")
            
            # Handle string data (convert to dict if it's JSON)
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    st.error(f"Failed to parse data as JSON for URL {i}")
                    continue
            
            if isinstance(data, dict):
                if 'listings' in data and isinstance(data['listings'], list):
                    df = pd.DataFrame(data['listings'])
                else:
                    # If 'listings' is not in the dict or not a list, use the entire dict
                    df = pd.DataFrame([data])
            elif hasattr(data, 'listings') and isinstance(data.listings, list):
                # Handle the case where data is a Pydantic model
                listings = [item.dict() for item in data.listings]
                df = pd.DataFrame(listings)
            else:
                st.error(f"Unexpected data format for URL {i}")
                continue
            
            # Display the dataframe
            st.dataframe(df, use_container_width=True)

        # Download options
        st.subheader("Download Options")
        col1, col2 = st.columns(2)
        with col1:
            json_data = json.dumps(all_data, default=lambda o: o.dict() if hasattr(o, 'dict') else str(o), indent=4)
            st.download_button(
                "Download JSON",
                data=json_data,
                file_name="scraped_data.json"
            )
        with col2:
            # Convert all data to a single DataFrame
            all_listings = []
            for data in all_data:
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                if isinstance(data, dict) and 'listings' in data:
                    all_listings.extend(data['listings'])
                elif hasattr(data, 'listings'):
                    all_listings.extend([item.dict() for item in data.listings])
                else:
                    all_listings.append(data)
            
            combined_df = pd.DataFrame(all_listings)
            st.download_button(
                "Download CSV",
                data=combined_df.to_csv(index=False),
                file_name="scraped_data.csv"
            )

        st.success(f"Scraping completed. Results saved in {output_folder}")

    # Add pagination details to sidebar
    if pagination_info and use_pagination:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Pagination Details")
        st.sidebar.markdown(f"**Number of Page URLs:** {len(pagination_info['page_urls'])}")

        st.markdown("---")
        st.subheader("Pagination Information")
        pagination_df = pd.DataFrame(pagination_info["page_urls"], columns=["Page URLs"])
        
        st.dataframe(
            pagination_df,
            column_config={
                "Page URLs": st.column_config.LinkColumn("Page URLs")
            },use_container_width=True
        )

        # Create columns for download buttons
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download Pagination JSON", 
                data=json.dumps(pagination_info["page_urls"], indent=4), 
                file_name=f"pagination_urls.json"
            )
        with col2:
            st.download_button(
                "Download Pagination CSV", 
                data=pagination_df.to_csv(index=False), 
                file_name=f"pagination_urls.csv"
            )
       

# Add a clear results button
if st.sidebar.button("Clear Results"):
    st.session_state['results'] = None
    st.session_state['perform_scrape'] = False
    st.rerun()